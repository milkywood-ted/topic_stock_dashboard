"""DataView — 그 자체로 의미 있는 데이터·통계 제공.

티어/그룹을 상속 계층의 View 오브젝트로 표현한다.
tier 분류는 DataView가 소유한다 — 스냅샷에 저장하지 않고 뷰 시점에 도출:
마스터 종목 = StockMeta.tier, 그룹 전용 종목 = TIER_GROUP.
차트를 그리기 위한 변환(정규화·robustY축·PER floor 등)은 여기 없다 — 그건 ChartDrawer(프런트).
"""

# tier 분류 어휘 (DataView 소유)
TIERS = ["1차", "2차", "3차"]   # AI 수혜 분류
TIER_GROUP = "그룹"             # 그룹 전용 종목(수혜 티어 아님)


def _distribution(rows: list) -> dict:
    """등락률 분포 버킷 카운트 (대시보드 히스토그램용)."""
    buckets = {"≤-3%": 0, "-3~-1%": 0, "-1~0%": 0, "0~+1%": 0, "+1~+3%": 0, "≥+3%": 0}
    for d in rows:
        v = d.get("change_pct")
        if v is None:
            continue
        if   v <= -3: buckets["≤-3%"]   += 1
        elif v <= -1: buckets["-3~-1%"] += 1
        elif v <   0: buckets["-1~0%"]  += 1
        elif v <=  1: buckets["0~+1%"]  += 1
        elif v <=  3: buckets["+1~+3%"] += 1
        else:         buckets["≥+3%"]   += 1
    return buckets


class DataView:
    """구성원 스냅샷의 재가공·통계. 서브클래스가 snapshots()를 정의한다.

    snaps(미리 가져온 전체 최신 스냅샷)를 주입하면 중복 쿼리를 피한다.
    """
    def __init__(self, store, snaps: list | None = None):
        self.store = store
        self._all = snaps
        self._tmap = None

    def _latest_all(self) -> list:
        if self._all is None:
            self._all = self.store.latest_snapshots()
        return self._all

    def _tier_map(self) -> dict:
        """ticker → tier (마스터 종목만; DataStore에서 주입)."""
        if self._tmap is None:
            self._tmap = {m.ticker: m.tier for m in self.store.active_metas()}
        return self._tmap

    def tier_of(self, ticker: str) -> str:
        """마스터 종목이면 그 tier, 아니면(그룹 전용) TIER_GROUP."""
        return self._tier_map().get(ticker, TIER_GROUP)

    # 서브클래스에서 구현
    def snapshots(self) -> list:
        raise NotImplementedError

    def rows(self) -> list:
        return [self.to_dict(s) for s in self.snapshots()]

    def summary(self) -> dict:
        rows = self.rows()
        changes = [d["change_pct"] for d in rows if d["change_pct"] is not None]
        return {
            "count":      len(rows),
            "avg_change": round(sum(changes) / len(changes), 2) if changes else 0,
            "gainers":    sum(1 for v in changes if v > 0),
            "losers":     sum(1 for v in changes if v < 0),
        }

    def to_dict(self, s) -> dict:
        """스냅샷 → 뷰 dict (tier는 뷰 시점 도출)."""
        week52_ret = None
        if s.week52_low and s.week52_high and s.week52_low > 0:
            week52_ret = round((s.price - s.week52_low) / s.week52_low * 100, 1) if s.price else None
        return {
            "ticker":       s.ticker,
            "name":         s.name,
            "tier":         self.tier_of(s.ticker),
            "sector":       s.sector,
            "market":       s.market,
            "price":        s.price,
            "change_pct":   s.change_pct,
            "mkt_cap":      s.mkt_cap,
            "mkt_cap_b":    round(s.mkt_cap / 1e9, 1) if s.mkt_cap else None,
            "pe_ratio":     round(s.pe_ratio, 1) if s.pe_ratio else None,
            "week52_high":  s.week52_high,
            "week52_low":   s.week52_low,
            "week52_ret":   week52_ret,
            "collected_at": s.collected_at.strftime("%Y-%m-%d %H:%M") if s.collected_at else None,
        }


class AllView(DataView):
    """전체 종목 (대시보드)."""
    def snapshots(self) -> list:
        return self._latest_all()

    def distribution(self) -> dict:
        return _distribution(self.rows())


class TierView(DataView):
    """특정 티어 종목."""
    tier = None

    def __init__(self, store, tier=None, snaps=None):
        super().__init__(store, snaps)
        if tier is not None:
            self.tier = tier

    def snapshots(self) -> list:
        # 종목의 도출 tier가 이 뷰의 tier와 일치하는 것만
        return [s for s in self._latest_all() if self.tier_of(s.ticker) == self.tier]


class Tier1View(TierView):
    tier = TIERS[0]


class Tier2View(TierView):
    tier = TIERS[1]


class Tier3View(TierView):
    tier = TIERS[2]


class GroupView(DataView):
    """특정 사용자 그룹 종목."""
    def __init__(self, store, group_id: int, snaps=None):
        super().__init__(store, snaps)
        self.group_id = group_id

    def snapshots(self) -> list:
        tickers = {m.ticker for m in self.store.members_of(self.group_id)}
        return [s for s in self._latest_all() if s.ticker in tickers]


class Catalog:
    """메타+그룹 통합 종목 카탈로그.

    전체 종목 목록(분류) 제공 — 티어/그룹 '뷰 집계'와 성격이 달라 별도 개념으로 둔다.
    """
    def __init__(self, store):
        self.store = store

    def known_stocks(self) -> dict:
        """{ticker: {name, tier, market, source}} — StockMeta 우선, 없으면 GroupStock."""
        result = {}
        for s in self.store.active_metas():
            result[s.ticker] = {"name": s.name, "tier": s.tier, "market": s.market, "source": "meta"}
        for s in self.store.all_group_stocks():
            if s.ticker not in result:
                result[s.ticker] = {"name": s.name, "tier": TIER_GROUP, "market": s.market, "source": "group"}
        return result


class MetricSeriesView:
    """단일 종목의 시계열 지표(가격·등락·PER·PBR·CAPEX·FCF·주주환원율).

    '여러 종목의 최신 스냅샷 집계'인 DataView 상속 계층과 달리 '한 종목의 시계열'이라
    Catalog처럼 별도 뷰로 둔다. 차트용 변환(정규화·robustY 등)이 아니라 그 자체로
    의미 있는 데이터다 — 차트 변환은 ChartDrawer(프런트) 소관.
    기간→일수(days) 변환은 라우트(차트 기간 어휘) 소관이라 호출자가 days를 넘긴다.
    """
    def __init__(self, store, ticker: str, days: int = 90):
        self.store  = store
        self.ticker = ticker
        self.days   = days

    def rows(self) -> list:
        """시간순 시계열 포인트 리스트."""
        return [self._to_point(s) for s in self.store.price_history(self.ticker, self.days)]

    @staticmethod
    def _to_point(s) -> dict:
        return {
            "date":         s.collected_at.strftime("%Y-%m-%d") if s.collected_at else None,
            "price":        s.price,
            "change_pct":   s.change_pct,
            "per":          round(s.pe_ratio, 2)     if s.pe_ratio     else None,
            "pbr":          round(s.pbr, 2)          if s.pbr          else None,
            "capex":        round(s.capex, 0)        if s.capex        else None,
            "fcf":          round(s.fcf, 0)          if s.fcf          else None,
            "payout_ratio": round(s.payout_ratio, 1) if s.payout_ratio else None,
        }
