"""DashboardController — 대시보드·차트·종목목록 조회 오케스트레이션.

HTTP 무관: 페이지는 '템플릿 컨텍스트 dict', API는 데이터를 반환한다.
TemplateResponse·기간어휘→일수 변환은 라우트 소관.
"""
import json

from app.DataView import AllView, TierView, Catalog, MetricSeriesView, TIERS


class DashboardController:
    def __init__(self, store):
        self.store = store

    # ── 페이지 컨텍스트 ────────────────────────────────────
    def dashboard_context(self) -> dict:
        """index.html 템플릿 변수."""
        all_view = AllView(self.store)
        snaps    = all_view.snapshots()          # 전체 최신 (1회 쿼리)
        data     = all_view.rows()
        overall  = all_view.summary()
        tier_summary = {t: TierView(self.store, t, snaps).summary() for t in TIERS}
        last_log = self.store.latest_log()

        summary_json = json.dumps({
            "overall":      overall,
            "tiers":        tier_summary,
            "distribution": all_view.distribution(),
        }, ensure_ascii=False)

        return {
            "stocks":       data,
            "total":        overall["count"],
            "gainers":      overall["gainers"],
            "losers":       overall["losers"],
            "last_collect": last_log.collected_at.strftime("%Y-%m-%d %H:%M UTC") if last_log else "없음",
            "stocks_json":  json.dumps(data, ensure_ascii=False),
            "summary_json": summary_json,
        }

    def chart_context(self) -> dict:
        """chart.html 템플릿 변수 (종목·그룹 JSON)."""
        known = Catalog(self.store).known_stocks()
        stocks_list = [{"ticker": t, "name": v["name"], "tier": v["tier"]} for t, v in known.items()]
        members = self.store.all_members()
        groups_list = [
            {"id": g.id, "name": g.name,
             "tickers": [m.ticker for m in members if m.group_id == g.id]}
            for g in self.store.all_groups()
        ]
        return {
            "stocks_json": json.dumps(stocks_list, ensure_ascii=False),
            "groups_json": json.dumps(groups_list, ensure_ascii=False),
        }

    def groups_page_context(self) -> dict:
        """groups.html 템플릿 변수 (통합 카탈로그 JSON)."""
        known = Catalog(self.store).known_stocks()
        return {"stocks_json": json.dumps(
            [{"ticker": t, **v} for t, v in known.items()], ensure_ascii=False)}

    # ── API 데이터 ─────────────────────────────────────────
    def stocks(self) -> list:
        """전체 종목 최신 행."""
        return AllView(self.store).rows()

    def summary(self) -> dict:
        """티어별 요약 통계."""
        snaps = self.store.latest_snapshots()
        return {t: TierView(self.store, t, snaps).summary() for t in TIERS}

    def history(self, ticker: str, days: int) -> list:
        """단일 종목 시계열 지표 (days는 라우트가 기간어휘에서 변환)."""
        return MetricSeriesView(self.store, ticker.upper(), days).rows()
