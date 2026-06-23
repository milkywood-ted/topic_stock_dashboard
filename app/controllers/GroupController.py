"""GroupController — 사용자 그룹·구성원·그룹종목 데이터 오케스트레이션.

HTTP 무관: 데이터 반환, 실패는 도메인 예외(NotFound/Conflict/Validation).
"""
from app.DataView import Catalog, TIER_GROUP
from app.Fetcher import Fetcher, BACKFILL_PERIODS
from app.errors import NotFoundError, ConflictError, ValidationError


class GroupController:
    def __init__(self, store):
        self.store = store
        self.fetcher = Fetcher(store)

    def _known(self) -> dict:
        return Catalog(self.store).known_stocks()

    # ── 그룹 CRUD ──────────────────────────────────────────
    def list_groups(self) -> list:
        """그룹 + 구성원(이름·tier 보강) 목록."""
        members = self.store.all_members()
        known   = self._known()
        result  = []
        for g in self.store.all_groups():
            m_list = [m for m in members if m.group_id == g.id]
            result.append({
                "id": g.id, "name": g.name, "note": g.note or "",
                "members": [
                    {"ticker": m.ticker,
                     "name": known.get(m.ticker, {}).get("name", m.ticker),
                     "tier": known.get(m.ticker, {}).get("tier", TIER_GROUP)}
                    for m in m_list
                ],
            })
        return result

    def create_group(self, name: str, note: str = "") -> dict:
        """그룹 생성. 중복명은 ConflictError."""
        name = name.strip()
        if self.store.group_by_name(name):
            raise ConflictError("이미 존재하는 그룹명입니다")
        g = self.store.create_group(name, note.strip())
        return {"id": g.id, "name": g.name}

    def delete_group(self, group_id: int) -> dict:
        """그룹 삭제. 없으면 NotFoundError."""
        if not self.store.delete_group(group_id):
            raise NotFoundError("그룹 없음")
        return {"status": "deleted"}

    def rename_group(self, group_id: int, name: str, note: str = "") -> dict:
        """그룹명·노트 수정. 없으면 NotFoundError."""
        g = self.store.rename_group(group_id, name.strip(), note.strip())
        if not g:
            raise NotFoundError("그룹 없음")
        return {"id": g.id, "name": g.name}

    # ── 구성원 ─────────────────────────────────────────────
    def add_member(self, group_id: int, ticker: str, name: str = "", market: str = "US") -> dict:
        """그룹에 종목 추가. 마스터·그룹종목 모두 없으면 등록+백필."""
        ticker = ticker.upper().strip()
        if not self.store.get_group(group_id):
            raise NotFoundError("그룹 없음")
        if self.store.member_exists(group_id, ticker):
            return {"status": "already_exists"}

        inserted = 0
        if not self.store.get_meta(ticker) and not self.store.get_group_stock(ticker):
            if not name:
                raise ValidationError("새 종목은 name 필드가 필요합니다")
            self.store.add_group_stock(ticker, name, market)
            inserted = self.fetcher.backfill_one(ticker, name, market, period="1y").get("inserted", 0)

        self.store.add_member(group_id, ticker)
        return {"status": "added", "ticker": ticker, "inserted": inserted}

    def remove_member(self, group_id: int, ticker: str) -> dict:
        """그룹에서 종목 제거."""
        self.store.remove_member(group_id, ticker)
        return {"status": "removed"}

    # ── 데이터 수집·소급 ───────────────────────────────────
    def fetch_data(self, group_id: int, period: str = "1y") -> dict:
        """그룹 내 전체 종목 과거 데이터 수집. 허용 외 period는 ValidationError."""
        if period not in BACKFILL_PERIODS:
            raise ValidationError(f"period는 {BACKFILL_PERIODS} 중 하나여야 합니다")
        members  = self.store.members_of(group_id)
        known    = self._known()
        inserted = 0
        for m in members:
            info   = known.get(m.ticker, {})
            name   = info.get("name", m.ticker)
            market = info.get("market", "US")
            inserted += self.fetcher.backfill_one(m.ticker, name, market, period=period).get("inserted", 0)
        return {"inserted": inserted, "period": period, "tickers": len(members)}

    def fill_metrics(self, group_id=None) -> dict:
        """그룹 종목 PER/PBR/CAPEX/FCF/주주환원율 소급 (None이면 전체 그룹)."""
        return self.fetcher.fill_group_metrics(group_id=group_id)

    def fix_kr_names(self) -> dict:
        """GroupStock 한국 종목명을 네이버 한국어로 일괄 수정."""
        group_stocks = self.store.kr_group_stocks()
        new_names = {}
        for gs in group_stocks:
            kr_name = Fetcher.fetch_kr_name(gs.ticker)
            if kr_name:
                new_names[gs.ticker] = kr_name
        updated = self.store.rename_group_stocks(new_names)
        return {"updated": updated, "total": len(group_stocks)}
