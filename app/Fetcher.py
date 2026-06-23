"""Fetcher — 외부 API(yfinance·네이버/야후) 수집.

가격·재무 수집은 인스턴스 메서드(`Fetcher(store)`, DataStore 경유 저장),
검색·이름조회는 외부 API만 쓰는 staticmethod(`Fetcher.search(q)`).
DB는 DataStore를 통해서만 접근한다 — Fetcher는 엔티티·세션을 모른다.
"""
import logging
import re
from datetime import datetime, timezone
from types import SimpleNamespace

import yfinance as yf
import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# 과거 데이터 백필에 허용되는 기간 (yfinance period 값) — Fetcher가 권위
BACKFILL_PERIODS = {"6mo", "1y", "2y", "5y", "max"}

# ── yfinance 재무제표 행 이름 후보 (버전·종목별로 명칭이 달라 우선순위 리스트) ──
CF_CAPEX_KEYS     = ["Capital Expenditure", "Purchase Of Property Plant And Equipment"]
CF_OCF_KEYS       = ["Operating Cash Flow", "Cash From Operations"]
CF_FCF_KEY        = "Free Cash Flow"
CF_DIVIDEND_KEYS  = ["Payment Of Dividends", "Cash Dividends Paid"]
CF_BUYBACK_KEYS   = ["Repurchase Of Capital Stock", "Common Stock Repurchased"]
IS_EPS_KEYS       = ["Diluted EPS", "Basic EPS"]
IS_NETINCOME_KEYS = ["Net Income", "Net Income Common Stockholders"]
BS_EQUITY_KEYS    = ["Stockholders Equity", "Common Stock Equity",
                     "Total Equity Gross Minority Interest"]
BS_SHARES_KEYS    = ["Ordinary Shares Number", "Share Issued"]

NAVER_SEARCH_URL = "https://m.stock.naver.com/front-api/search"
NAVER_PRICE_URL  = "https://m.stock.naver.com/api/stock/{code}/price"
YAHOO_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
UA = {"User-Agent": "Mozilla/5.0"}


class Fetcher:
    def __init__(self, store):
        self.store = store

    # ── 일일 수집 ──────────────────────────────────────────
    def collect_all(self) -> dict:
        """전 종목 일일 수집. US=yfinance 일괄, KR(.KS/.KQ)=네이버 일별 시세.

        대상 = 활성 마스터 종목(StockMeta) + 그룹 전용 종목(GroupStock).
        KR은 야후 `.KS` 종가 지연(거래일 Close가 NaN으로 늦게 확정)으로 최신일을
        놓치므로 네이버에서 당일 종가를 받는다. 재무지표는 양쪽 다 야후 분기재무.
        """
        # 마스터(MetaDTO: name/sector/market) + 그룹 전용(sector 없음 → None 래핑)
        meta_map = {m.ticker: m for m in self.store.active_metas()}
        for gs in self.store.all_group_stocks():
            if gs.ticker not in meta_map:
                meta_map[gs.ticker] = SimpleNamespace(
                    name=gs.name, sector=None, market=gs.market)
        tickers = list(meta_map)
        us_tickers = [t for t in tickers if not t.endswith((".KS", ".KQ"))]
        kr_tickers = [t for t in tickers if t.endswith((".KS", ".KQ"))]

        logger.info(f"수집 시작: {len(tickers)}개 (US {len(us_tickers)} · KR {len(kr_tickers)})")

        now = datetime.now(timezone.utc)
        success, failed = 0, 0

        s, f = self._collect_us(us_tickers, meta_map, now)
        success += s
        failed  += f

        for ticker in kr_tickers:
            status = self._collect_kr_one(ticker, meta_map[ticker])
            if   status == "stored": success += 1
            elif status == "failed": failed  += 1
            # "skipped"는 성공·실패 어디에도 더하지 않음(US 루프의 continue와 동일)

        self.store.add_log(
            collected_at=now, total=len(tickers), success=success, failed=failed,
            message=f"수집 완료 {success}/{len(tickers)}",
        )
        self.store.commit()

        logger.info(f"수집 완료: 성공 {success}, 실패 {failed}")
        return {"success": success, "failed": failed, "total": len(tickers)}

    def _collect_us(self, tickers: list, meta_map: dict, now) -> tuple:
        """US 종목 yfinance 일괄 수집. (성공수, 실패수) 반환."""
        if not tickers:
            return 0, 0
        try:
            raw = yf.download(
                tickers, period="5d", interval="1d", group_by="ticker",
                auto_adjust=True, progress=False, threads=True,
            )
        except Exception as e:
            logger.error(f"yfinance 다운로드 실패: {e}")
            return 0, len(tickers)

        success, failed = 0, 0
        for ticker in tickers:
            try:
                meta = meta_map[ticker]

                # 단일 종목일 때와 복수 종목일 때 DataFrame 구조가 다름
                if len(tickers) == 1:
                    df = raw
                else:
                    if ticker not in raw.columns.get_level_values(0):
                        raise KeyError(f"{ticker} 데이터 없음")
                    df = raw[ticker]

                df = df.dropna(how="all")
                # Close가 NaN인 행 제거 (장중·데이터 지연으로 아직 확정 안 된 당일 데이터)
                if "Close" in df.columns:
                    df = df.dropna(subset=["Close"])
                if df.empty:
                    raise ValueError("빈 데이터")

                latest = df.iloc[-1]
                prev   = df.iloc[-2] if len(df) >= 2 else df.iloc[-1]

                # 이미 같은 거래일 데이터가 있으면 스킵 (주말·공휴일 중복 방지)
                actual_date = df.index[-1].date()
                latest_stored = self.store.latest_snapshot_date(ticker)
                if latest_stored and latest_stored.date() >= actual_date:
                    logger.info(f"  ⚡ {ticker} 중복 스킵 ({actual_date} 이미 존재)")
                    continue

                price      = float(latest["Close"])
                price_prev = float(prev["Close"])
                change_pct = ((price - price_prev) / price_prev * 100) if price_prev else 0.0
                volume     = float(latest.get("Volume", 0) or 0)

                info = {}
                try:
                    info = yf.Ticker(ticker).info or {}
                except Exception:
                    pass
                mkt_cap     = info.get("marketCap")
                week52_high = info.get("fiftyTwoWeekHigh")
                week52_low  = info.get("fiftyTwoWeekLow")

                self._store_snapshot(
                    ticker, meta,
                    price=price, price_prev=price_prev, change_pct=change_pct,
                    volume=volume,
                    mkt_cap     = float(mkt_cap) if mkt_cap else None,
                    week52_high = float(week52_high) if week52_high else None,
                    week52_low  = float(week52_low) if week52_low else None,
                    collected_at=now,
                )
                success += 1
                logger.info(f"  ✓ {ticker} ({meta.name}): ${price:.2f} ({change_pct:+.2f}%)")

            except Exception as e:
                failed += 1
                logger.warning(f"  ✗ {ticker}: {e}")
        return success, failed

    def _collect_kr_one(self, ticker: str, meta) -> str:
        """KR 종목 1건을 네이버 일별 시세로 수집. 'stored'|'skipped'|'failed' 반환."""
        try:
            bars = self._naver_daily_prices(ticker.split(".")[0], size=5)  # 최신순
            if not bars:
                raise ValueError("네이버 시세 없음")

            latest      = bars[0]
            actual_date = latest["date"]
            latest_stored = self.store.latest_snapshot_date(ticker)
            if latest_stored and latest_stored.date() >= actual_date:
                logger.info(f"  ⚡ {ticker} 중복 스킵 ({actual_date} 이미 존재)")
                return "skipped"

            price      = latest["close"]
            price_prev = bars[1]["close"] if len(bars) >= 2 else price

            # 시총·52주는 야후 info (일별 종가와 달리 지연 영향이 적음, best effort)
            mkt_cap = week52_high = week52_low = None
            try:
                info = yf.Ticker(ticker).info or {}
                mkt_cap     = info.get("marketCap")
                week52_high = info.get("fiftyTwoWeekHigh")
                week52_low  = info.get("fiftyTwoWeekLow")
            except Exception:
                pass

            self._store_snapshot(
                ticker, meta,
                price=price, price_prev=price_prev, change_pct=latest["change_pct"],
                volume=latest["volume"],
                mkt_cap     = float(mkt_cap) if mkt_cap else None,
                week52_high = float(week52_high) if week52_high else None,
                week52_low  = float(week52_low) if week52_low else None,
                collected_at=datetime(actual_date.year, actual_date.month, actual_date.day,
                                      12, 0, 0, tzinfo=timezone.utc),
            )
            logger.info(f"  ✓ {ticker} ({meta.name}) [naver]: ₩{price:,.0f} ({latest['change_pct']:+.2f}%)")
            return "stored"
        except Exception as e:
            logger.warning(f"  ✗ {ticker}: {e}")
            return "failed"

    def _store_snapshot(self, ticker, meta, *, price, price_prev, change_pct,
                        volume, mkt_cap, week52_high, week52_low, collected_at):
        """가격·시장지표 + 야후 분기재무 계산지표로 스냅샷 1건 stage(호출자 commit).

        PER/PBR/CAPEX/FCF/payout은 가격 출처(야후/네이버)와 무관하게
        _quarterly_fundamentals(야후 분기재무)의 '최신 분기'로 동일 규칙 도출 —
        US·KR·백필·소급이 모두 같은 방법론을 공유한다.
        """
        on       = collected_at.date()
        fm       = self._quarterly_fundamentals(ticker)
        ttm_eps  = self._calc_ttm_eps(on, fm["eps"])
        bps      = self._calc_latest(on, fm["bps"])
        self.store.add_snapshot(
            ticker       = ticker,
            name         = meta.name,
            sector       = meta.sector,
            market       = meta.market,
            price        = price,
            price_prev   = price_prev,
            change_pct   = round(change_pct, 2),
            volume       = volume,
            mkt_cap      = mkt_cap,
            pe_ratio     = round(price / ttm_eps, 2) if ttm_eps and ttm_eps != 0 else None,
            pbr          = round(price / bps, 2)     if bps and bps > 0          else None,
            capex        = self._calc_latest(on, fm["capex"]),
            fcf          = self._calc_latest(on, fm["fcf"]),
            payout_ratio = self._calc_latest(on, fm["payout"]),
            week52_high  = week52_high,
            week52_low   = week52_low,
            collected_at = collected_at,
        )

    # ── 백필 ───────────────────────────────────────────────
    def backfill_all(self, period: str = "1y") -> dict:
        """활성 종목 과거 데이터 일괄 수집 (중복 날짜 스킵)"""
        stocks = self.store.active_metas()
        tickers = [s.ticker for s in stocks]
        meta_map = {s.ticker: s for s in stocks}

        logger.info(f"과거 데이터 백필 시작: {len(tickers)}개 종목, period={period}")

        try:
            raw = yf.download(
                tickers, period=period, interval="1d", group_by="ticker",
                auto_adjust=True, progress=False, threads=True,
            )
        except Exception as e:
            logger.error(f"yfinance 다운로드 실패: {e}")
            return {"inserted": 0, "skipped": 0, "error": str(e)}

        existing_set = self.store.snapshot_keys()
        inserted, skipped = 0, 0

        for ticker in tickers:
            try:
                meta = meta_map[ticker]
                if len(tickers) == 1:
                    df = raw
                else:
                    if ticker not in raw.columns.get_level_values(0):
                        continue
                    df = raw[ticker]

                df = df.dropna(how="all")
                if df.empty:
                    continue

                rows_list = list(df.iterrows())
                # 새로 넣을 날짜가 없으면 재무 조회를 생략(공백 없을 때 빠른 통과)
                if all((ticker, idx.strftime("%Y-%m-%d")) in existing_set
                       for idx, _ in rows_list):
                    skipped += len(rows_list)
                    continue

                logger.info(f"  {ticker} 재무 데이터 조회 중...")
                fm = self._quarterly_fundamentals(ticker)

                for i, (idx, row) in enumerate(rows_list):
                    date_str = idx.strftime("%Y-%m-%d")
                    if (ticker, date_str) in existing_set:
                        skipped += 1
                        continue

                    price = float(row["Close"])
                    prev_price = float(rows_list[i - 1][1]["Close"]) if i > 0 else price
                    change_pct = round((price - prev_price) / prev_price * 100, 2) if prev_price else 0.0
                    volume = float(row.get("Volume", 0) or 0)

                    date     = idx.date()
                    ttm_eps  = self._calc_ttm_eps(date, fm["eps"])
                    bps      = self._calc_latest(date, fm["bps"])
                    per      = round(price / ttm_eps, 2) if ttm_eps and ttm_eps != 0 else None
                    pbr_val  = round(price / bps, 2) if bps and bps > 0 else None

                    self.store.add_snapshot(
                        ticker       = ticker,
                        name         = meta.name,
                        sector       = meta.sector,
                        market       = meta.market,
                        price        = price,
                        price_prev   = prev_price,
                        change_pct   = change_pct,
                        volume       = volume,
                        mkt_cap      = None,
                        pe_ratio     = per,
                        pbr          = pbr_val,
                        capex        = self._calc_latest(date, fm["capex"]),
                        fcf          = self._calc_latest(date, fm["fcf"]),
                        payout_ratio = self._calc_latest(date, fm["payout"]),
                        week52_high  = None,
                        week52_low   = None,
                        collected_at = datetime(idx.year, idx.month, idx.day, 12, 0, 0, tzinfo=timezone.utc),
                    )
                    existing_set.add((ticker, date_str))
                    inserted += 1

            except Exception as e:
                logger.warning(f"  ✗ {ticker} 백필 실패: {e}")

        self.store.commit()
        logger.info(f"백필 완료: 삽입 {inserted}, 스킵(중복) {skipped}")
        return {"inserted": inserted, "skipped": skipped, "total_tickers": len(tickers), "period": period}

    def backfill_one(self, ticker: str, name: str, market: str = "US", period: str = "1y") -> dict:
        """그룹 전용 종목 단일 백필"""
        try:
            raw = yf.download(ticker, period=period, interval="1d",
                              auto_adjust=True, progress=False, threads=False)
        except Exception as e:
            return {"inserted": 0, "error": str(e)}

        if raw is None or raw.empty:
            return {"inserted": 0, "error": "데이터 없음"}

        # yfinance 버전에 따라 단일 티커도 MultiIndex 컬럼이 될 수 있음
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)

        existing = self.store.snapshot_dates(ticker)
        inserted = 0
        rows_list = list(raw.iterrows())
        for i, (idx, row) in enumerate(rows_list):
            date_str = idx.strftime("%Y-%m-%d")
            if date_str in existing:
                continue
            price = float(row["Close"])
            prev  = float(rows_list[i - 1][1]["Close"]) if i > 0 else price
            self.store.add_snapshot(
                ticker=ticker, name=name, sector=None, market=market,
                price=price, price_prev=prev,
                change_pct=round((price - prev) / prev * 100, 2) if prev else 0.0,
                volume=float(row.get("Volume", 0) or 0),
                mkt_cap=None, pe_ratio=None, pbr=None,
                capex=None, fcf=None, payout_ratio=None,
                week52_high=None, week52_low=None,
                collected_at=datetime(idx.year, idx.month, idx.day, 12, 0, 0, tzinfo=timezone.utc),
            )
            existing.add(date_str)
            inserted += 1

        self.store.commit()
        logger.info(f"  ✓ {ticker} ({name}): {inserted}개 삽입")
        return {"inserted": inserted}

    def backfill_group_stocks(self, period: str = "1y") -> dict:
        """그룹 전용 종목 전체 과거 데이터 일괄 백필 (가격 공백 메움)."""
        groups = self.store.all_group_stocks()
        inserted = 0
        for gs in groups:
            inserted += self.backfill_one(gs.ticker, gs.name, gs.market, period=period).get("inserted", 0)
        return {"inserted": inserted, "tickers": len(groups)}

    # ── 기동 동기화 (공백 메움) ────────────────────────────
    def _gap_period(self) -> str:
        """가장 뒤처진 종목의 마지막 데이터 기준으로 backfill 기간 산정.

        공백(gap)을 덮을 최소 yfinance period를 고른다 — 불필요한 과다 다운로드 방지.
        데이터가 없으면 초기 적재용 '1y'.
        """
        snaps = self.store.latest_snapshots()
        if not snaps:
            return "1y"
        oldest = min(s.collected_at for s in snaps if s.collected_at).date()
        gap = (datetime.now(timezone.utc).date() - oldest).days
        for days, period in [(5, "5d"), (28, "1mo"), (85, "3mo"),
                             (175, "6mo"), (360, "1y"), (720, "2y")]:
            if gap <= days:
                return period
        return "max"

    def sync_to_today(self) -> dict:
        """기동 시 현재시각까지 동기화 — 빠진 거래일을 모두 메운다.

        ① collect_all(): 오늘 시세(시총·52주·네이버 KR 포함)
        ② backfill(gap 기간): 마스터+그룹의 빠진 과거일 채움(중복은 스킵).
        오늘은 ①이 먼저 저장하므로 ②는 그 이전 공백만 메운다.
        """
        collected = self.collect_all()
        period = self._gap_period()
        logger.info(f"공백 메움 백필 시작 (period={period})")
        master = self.backfill_all(period=period)
        group  = self.backfill_group_stocks(period=period)
        filled = master.get("inserted", 0) + group.get("inserted", 0)
        logger.info(f"공백 메움 완료: {filled}개 거래일 보충 (period={period})")
        return {"collected": collected, "filled": filled, "period": period}

    # ── 지표 소급 ──────────────────────────────────────────
    def fill_metrics(self) -> dict:
        """StockMeta 종목 스냅샷의 PER/PBR/CAPEX/FCF 소급 계산"""
        return self._fill_for([s.ticker for s in self.store.active_metas()])

    def fill_group_metrics(self, group_id: int | None = None) -> dict:
        """GroupStock 종목 스냅샷 소급. group_id=None이면 전체 그룹."""
        if group_id is not None:
            tickers = list({m.ticker for m in self.store.members_of(group_id)})
        else:
            tickers = list({s.ticker for s in self.store.all_group_stocks()})
        return self._fill_for(tickers)

    def _fill_for(self, tickers: list) -> dict:
        total_updated = 0
        for ticker in tickers:
            logger.info(f"  {ticker} 재무 데이터 조회 중...")
            fm = self._quarterly_fundamentals(ticker)
            if not any(fm.values()):
                logger.warning(f"    재무 데이터 없음: {ticker}")
                continue

            snaps = self.store.snapshots_missing_metrics(ticker)
            for snap in snaps:
                updates = self._compute_fundamentals(snap, fm)
                if updates:
                    self.store.update_snapshot_metrics(snap.id, **updates)
            self.store.commit()
            total_updated += len(snaps)
            logger.info(f"    ✓ {ticker}: {len(snaps)}개 스냅샷 처리")

        return {"updated": total_updated, "tickers": len(tickers)}

    @classmethod
    def _compute_fundamentals(cls, snap, fm) -> dict:
        """스냅샷(DTO)의 null 지표를 분기 재무(fm)로 채울 값 dict 계산.

        DTO는 불변이므로 변이하지 않고 {컬럼: 값}만 반환 — 저장은 DataStore가.
        """
        date = snap.collected_at.date()
        updates = {}
        if snap.pe_ratio is None and fm["eps"]:
            ttm = cls._calc_ttm_eps(date, fm["eps"])
            if ttm and ttm != 0 and snap.price:
                updates["pe_ratio"] = round(snap.price / ttm, 2)
        if snap.pbr is None and fm["bps"]:
            bps = cls._calc_latest(date, fm["bps"])
            if bps and bps > 0 and snap.price:
                updates["pbr"] = round(snap.price / bps, 2)
        if snap.capex is None and fm["capex"]:
            capex = cls._calc_latest(date, fm["capex"])
            if capex is not None:
                updates["capex"] = capex
        if snap.fcf is None and fm["fcf"]:
            fcf = cls._calc_latest(date, fm["fcf"])
            if fcf is not None:
                updates["fcf"] = fcf
        if snap.payout_ratio is None and fm["payout"]:
            payout = cls._calc_latest(date, fm["payout"])
            if payout is not None:
                updates["payout_ratio"] = payout
        return updates

    # ── 재무 시계열 (내부) ─────────────────────────────────
    @staticmethod
    def _quarterly_fundamentals(ticker: str) -> dict:
        """분기 재무 시계열을 종류별로 반환.

        반환: {"eps": {date: float}, "bps": {...}, "capex": {...},
               "fcf": {...}, "payout": {...}}
        """
        eps_map, bps_map, capex_map, fcf_map, payout_map = {}, {}, {}, {}, {}
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
            shares_info = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
            ni_map, div_map, buyback_map = {}, {}, {}

            def _d(col):
                return col.date() if hasattr(col, "date") else pd.Timestamp(col).date()

            # ── EPS + 순이익 ──
            income = t.quarterly_income_stmt
            if income is not None and not income.empty:
                eps_row = None
                for key in IS_EPS_KEYS:
                    if key in income.index:
                        eps_row = income.loc[key]; break
                if eps_row is None and shares_info:
                    for key in IS_NETINCOME_KEYS:
                        if key in income.index:
                            eps_row = income.loc[key] / shares_info; break
                if eps_row is not None:
                    for col, val in eps_row.items():
                        if pd.notna(val):
                            eps_map[_d(col)] = float(val)
                for key in IS_NETINCOME_KEYS:
                    if key in income.index:
                        for col, val in income.loc[key].items():
                            if pd.notna(val):
                                ni_map[_d(col)] = float(val)
                        break

            # ── BPS ──
            balance = t.quarterly_balance_sheet
            if balance is not None and not balance.empty:
                eq_row = None
                for key in BS_EQUITY_KEYS:
                    if key in balance.index:
                        eq_row = balance.loc[key]; break
                sh_row = None
                for key in BS_SHARES_KEYS:
                    if key in balance.index:
                        sh_row = balance.loc[key]; break
                if eq_row is not None:
                    for col, val in eq_row.items():
                        if pd.notna(val):
                            sh = None
                            if sh_row is not None:
                                sv = sh_row.get(col)
                                if sv is not None and pd.notna(sv):
                                    sh = float(sv)
                            if not sh:
                                sh = shares_info
                            if sh and sh > 0:
                                bps_map[_d(col)] = float(val) / sh

            # ── CAPEX · FCF · 배당 · 자사주매입 ──
            cf = t.quarterly_cashflow
            if cf is not None and not cf.empty:
                capex_row, ocf_row, fcf_row = None, None, None
                for key in CF_CAPEX_KEYS:
                    if key in cf.index:
                        capex_row = cf.loc[key]; break
                for key in CF_OCF_KEYS:
                    if key in cf.index:
                        ocf_row = cf.loc[key]; break
                if CF_FCF_KEY in cf.index:
                    fcf_row = cf.loc[CF_FCF_KEY]

                for key in CF_DIVIDEND_KEYS:
                    if key in cf.index:
                        for col, val in cf.loc[key].items():
                            if pd.notna(val) and val != 0:
                                div_map[_d(col)] = abs(float(val))
                        break
                for key in CF_BUYBACK_KEYS:
                    if key in cf.index:
                        for col, val in cf.loc[key].items():
                            if pd.notna(val) and val != 0:
                                buyback_map[_d(col)] = abs(float(val))
                        break

                for col in cf.columns:
                    d = _d(col)
                    if capex_row is not None and pd.notna(capex_row.get(col)):
                        capex_map[d] = abs(float(capex_row[col]))
                    if fcf_row is not None and pd.notna(fcf_row.get(col)):
                        fcf_map[d] = float(fcf_row[col])
                    elif (ocf_row is not None and capex_row is not None
                          and pd.notna(ocf_row.get(col)) and pd.notna(capex_row.get(col))):
                        fcf_map[d] = float(ocf_row[col]) + float(capex_row[col])

            # ── 주주환원율 ──
            for d in set(div_map) | set(buyback_map):
                total = div_map.get(d, 0) + buyback_map.get(d, 0)
                ni = ni_map.get(d)
                if ni and abs(ni) > 0 and total > 0:
                    payout_map[d] = round(total / abs(ni) * 100, 1)

        except Exception as e:
            logger.warning(f"  재무 데이터 조회 실패 ({ticker}): {e}")
        return {"eps": eps_map, "bps": bps_map, "capex": capex_map,
                "fcf": fcf_map, "payout": payout_map}

    @staticmethod
    def _calc_ttm_eps(date, eps_map):
        past = sorted(d for d in eps_map if d <= date)
        if not past:
            return None
        ttm = sum(eps_map[d] for d in past[-4:])
        return ttm if ttm != 0 else None

    @staticmethod
    def _calc_latest(date, val_map):
        """date 이전 가장 최근 값"""
        past = sorted(d for d in val_map if d <= date)
        return val_map[past[-1]] if past else None

    # ── KR 일별 시세 (네이버 — 야후 .KS 지연 우회) ─────────
    @staticmethod
    def _naver_daily_prices(code: str, size: int = 5) -> list:
        """네이버 KR 일별 시세 (최신순). 반환 [{date, close, change_pct, volume}, ...].

        code는 숫자부(.KS/.KQ 제외). 실패 시 빈 리스트.
        """
        try:
            res = requests.get(
                NAVER_PRICE_URL.format(code=code),
                params={"pageSize": size, "page": 1},
                headers=UA, timeout=5,
            )
            rows = res.json()
        except Exception:
            return []
        out = []
        for r in rows:
            try:
                ratio = r.get("fluctuationsRatio")
                out.append({
                    "date":       datetime.strptime(r["localTradedAt"], "%Y-%m-%d").date(),
                    "close":      float(str(r["closePrice"]).replace(",", "")),
                    "change_pct": float(ratio) if ratio not in (None, "") else 0.0,
                    "volume":     float(r.get("accumulatedTradingVolume") or 0),
                })
            except (ValueError, KeyError, TypeError):
                continue
        return out

    # ── 검색·이름조회 (외부 API only) ──────────────────────
    @staticmethod
    def _naver_search(query: str, size: int = 8) -> list:
        """네이버 증권 종목 검색 → items 리스트 (실패 시 빈 리스트)"""
        try:
            res = requests.get(
                NAVER_SEARCH_URL,
                params={"q": query, "target": "stock", "size": size, "page": 1},
                headers=UA, timeout=5,
            )
            data = res.json()
            if data.get("isSuccess"):
                return data.get("result", {}).get("items", [])
        except Exception:
            pass
        return []

    @staticmethod
    def search(q: str) -> list:
        """Yahoo Finance + 네이버 증권으로 종목명·티커 검색"""
        results, seen = [], set()

        def add(ticker, name, rtype, market):
            if ticker and name and ticker not in seen:
                results.append({"ticker": ticker, "name": name, "type": rtype, "market": market})
                seen.add(ticker)

        has_korean = bool(re.search("[가-힣]", q))

        # Yahoo (영문 검색어일 때만)
        if not has_korean:
            try:
                res = requests.get(
                    YAHOO_SEARCH_URL,
                    params={"q": q, "quotesCount": 8, "newsCount": 0},
                    headers=UA, timeout=5,
                )
                for item in res.json().get("quotes", []):
                    ticker = item.get("symbol", "")
                    name   = item.get("longname") or item.get("shortname", "")
                    market = "KR" if ticker.endswith((".KS", ".KQ")) else "US"
                    add(ticker, name, item.get("quoteType", ""), market)
            except Exception:
                pass

        # 네이버 (항상, 한글 검색에 특화)
        for item in Fetcher._naver_search(q, size=8):
            code      = item.get("code", "")
            name      = item.get("name", "")
            type_code = item.get("typeCode", "")
            is_kr     = item.get("nationCode") == "KOR"
            suffix    = ".KQ" if type_code == "KOSDAQ" else ".KS"
            ticker    = f"{code}{suffix}" if is_kr else code
            add(ticker, name, type_code, "KR" if is_kr else "US")

        return results[:10]

    @staticmethod
    def fetch_kr_name(ticker: str) -> str | None:
        """한국 종목 코드로 네이버에서 한국어 이름 조회"""
        code = ticker.split(".")[0]
        for item in Fetcher._naver_search(code, size=5):
            if item.get("code") == code:
                return item.get("name")
        return None

    @staticmethod
    def lookup_ticker(ticker: str) -> dict | None:
        """외부에서 종목명·시장 조회 (known 체크는 호출자가). 못 찾으면 None."""
        is_korean = ticker.endswith((".KS", ".KQ"))
        market = "KR" if is_korean else "US"
        name = None
        if is_korean:
            name = Fetcher.fetch_kr_name(ticker)
        if not name:
            try:
                info = yf.Ticker(ticker).info or {}
                name = info.get("longName") or info.get("shortName")
            except Exception:
                pass
        if not name:
            return None
        return {"name": name, "market": market}
