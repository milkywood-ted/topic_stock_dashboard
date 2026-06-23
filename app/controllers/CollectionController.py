"""CollectionController — 데이터 적재(수집·백필·소급·정리) 오케스트레이션.

HTTP 무관: 순수 파라미터를 받고 dict를 반환하거나 도메인 예외를 raise한다.
"""
from app.Fetcher import Fetcher, BACKFILL_PERIODS
from app.errors import ValidationError


class CollectionController:
    def __init__(self, store):
        self.store = store
        self.fetcher = Fetcher(store)

    def collect(self) -> dict:
        """전 종목 일일 수집 (마스터 + 그룹)."""
        return self.fetcher.collect_all()

    def sync(self) -> dict:
        """기동 동기화 — 오늘 수집 + 빠진 거래일 공백 메움(backfill)."""
        return self.fetcher.sync_to_today()

    def reset_snapshots(self) -> dict:
        """스냅샷·수집로그 전체 삭제 (종목 목록은 유지)."""
        self.store.reset_all()
        return {"status": "ok", "message": "스냅샷 및 수집 로그가 초기화되었습니다."}

    def cleanup_duplicates(self) -> dict:
        """(ticker, 날짜) 중복 스냅샷 제거."""
        return {"deleted": self.store.cleanup_duplicates()}

    def fill_metrics(self) -> dict:
        """기존 스냅샷에 PER/PBR/CAPEX/FCF/주주환원율 소급."""
        return self.fetcher.fill_metrics()

    def backfill(self, period: str = "1y") -> dict:
        """과거 데이터 일괄 수집. 허용 외 period는 ValidationError."""
        if period not in BACKFILL_PERIODS:
            raise ValidationError(f"period는 {BACKFILL_PERIODS} 중 하나여야 합니다")
        return self.fetcher.backfill_all(period=period)
