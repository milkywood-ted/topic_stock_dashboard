"""StockController — 종목 마스터 관리·조회·검색 오케스트레이션.

HTTP 무관: 데이터/컨텍스트 dict 반환, 실패는 도메인 예외(NotFoundError).
"""
from app.DataView import Catalog, TIER_GROUP
from app.Fetcher import Fetcher
from app.errors import NotFoundError


class StockController:
    def __init__(self, store):
        self.store = store

    def manage_context(self) -> dict:
        """manage.html 템플릿 변수 (종목 마스터 + 최근 로그)."""
        return {
            "stocks": self.store.all_metas_sorted(),
            "logs":   self.store.recent_logs(10),
        }

    def add_stock(self, ticker: str, name: str, tier: str,
                  sector: str = "", market: str = "US") -> dict:
        """종목 추가. 이미 있으면 재활성화."""
        ticker = ticker.upper().strip()
        if self.store.set_meta_active(ticker, True):
            return {"status": "reactivated", "ticker": ticker}
        self.store.add_meta(ticker=ticker, name=name, tier=tier,
                            sector=sector, market=market, active=1)
        return {"status": "added", "ticker": ticker}

    def toggle_stock(self, ticker: str) -> dict:
        """활성/비활성 토글. 없으면 NotFoundError."""
        stock = self.store.toggle_meta_active(ticker)
        if not stock:
            raise NotFoundError("종목 없음")
        return {"ticker": ticker, "active": stock.active}

    def ticker_info(self, ticker: str) -> dict:
        """종목 기본 정보 — known이면 카탈로그, 아니면 외부 조회. 못 찾으면 NotFoundError."""
        ticker = ticker.upper().strip()
        known  = Catalog(self.store).known_stocks()
        if ticker in known:
            return {"ticker": ticker, **known[ticker], "known": True}

        info = Fetcher.lookup_ticker(ticker)
        if not info:
            raise NotFoundError("종목을 찾을 수 없습니다")
        return {"ticker": ticker, "name": info["name"], "tier": TIER_GROUP,
                "market": info["market"], "known": False}

    def search(self, q: str) -> list:
        """Yahoo + 네이버 종목 검색 (외부 API only)."""
        return Fetcher.search(q)
