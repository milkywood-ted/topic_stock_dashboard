# 리팩토링 계획서 (검토 단계)

> 목표: 아래 **4개 오브젝트(행위 중심)** 로 소스를 모듈화·추상화한다.
> 이 문서는 ① 현재 코드 매핑(사실) ② 오브젝트별 제안 책임 ③ **결정 대기(확인 필요)** 로 구성된다.
> 결정 대기 항목이 정해진 뒤에 실행 항목(RF-xx)을 채워 하나씩 진행한다.

## 사용자 정의 4 오브젝트
1. **DataStore (데이터 저장·관리)** — 실제 데이터의 추가/업데이트/삭제/제공. 중복 확인도 담당.
2. **Fetcher (데이터 수집)** — yfinance·네이버 API로 데이터를 가져옴. **DataStore의 메서드를 통해** DB 업데이트·중복 확인.
3. **DataView (데이터 뷰)** — DataStore에서 데이터를 받아 view에 맞게 재가공. 1차/2차/3차 수혜종목·사용자 그룹이 각각 view. **계산·통계**를 담당.
4. **ChartDrawer (차트 렌더)** — DataView를 원하는 형태의 차트로 그림.

---

## 1. 현재 코드 → 4 오브젝트 매핑 (사실)

### DataStore 후보 (현재 흩어진 위치)
- `database.py`: 모델 6종(StockSnapshot, StockMeta, CollectLog, UserGroup, GroupMember, GroupStock), engine/session, `init_db`(+ALTER 마이그레이션), 상수(TIERS/TIER_GROUP)
- `collector.py`: `get_latest_snapshots`, `get_price_history`, `cleanup_duplicate_snapshots`, 그리고 `collect_all`/`backfill_*` 내부의 **중복확인·INSERT 로직**
- `main.py`: 라우트 안에 **산재한 `db.query(...)`** — 그룹 CRUD(create/delete/add_member/remove/rename), stock_meta CRUD(add/toggle), `_all_known_stocks`, `reset_snapshots`

### Fetcher 후보
- `collector.py`: `collect_all`, `backfill_history`, `backfill_ticker`, `_get_quarterly_fundamentals`, (보조: `_calc_ttm_eps`, `_calc_latest`), `fill_metrics`/`fill_group_metrics` (← **가져오기+저장 혼합**)
- `main.py`: `_naver_search`, `_fetch_kr_name`, `search_ticker`, `ticker_info` (네이버/야후 검색·이름조회)

### DataView 후보
- `main.py`: `snap_to_dict`, `api_summary`(티어 통계), `_all_known_stocks`(분류)
- `templates/index.html` JS: `updateSummary`, `drawCharts`용 집계(티어 평균·등락분포), `getFiltered`/`getSorted`(테이블 필터·정렬)
- `templates/chart.html` JS: 정규화(`updateChart` 내 norm), `robustYRange`, PER floor(`METRIC_CFG`), 메트릭 시계열 구성(`drawMetricChart`/`drawCombinedChart`의 데이터 가공부), `renderLegend` 계산

### ChartDrawer 후보
- `templates/index.html` JS: `drawCharts`(tierChart, distChart)
- `templates/chart.html` JS: `updateChart`, `drawMetricChart`, `drawCombinedChart`, 플러그인(`chartPlugin`, `makeEndLabelPlugin`), 공용 헬퍼(`baseTooltip`/`baseXScale`/`baseYScale`/`colorForTicker`/`applyHoverToChart`)

### 어디에도 안 맞는 5번째: 라우트(컨트롤러)
- `main.py`의 `@app.*` 핸들러 전체 — HTTP 요청을 받아 위 오브젝트를 **오케스트레이션**하는 역할. 4 오브젝트 어디에도 정확히 속하지 않음 → **결정 대기 Q3**.

---

## 2. 오브젝트별 제안 책임 (제안 · 미확정)

> 아래는 제안이며, "결정 대기"가 정해지면 확정한다.

- **DataStore**: 스냅샷 upsert(+중복확인), 스냅샷 조회(최신/이력), stock_meta CRUD, 그룹/그룹멤버/그룹종목 CRUD, known-stocks 통합 조회. (순수 DB 계층, 외부 API 의존 없음)
- **Fetcher**: yfinance 가격·재무 fetch, 네이버/야후 검색·이름조회. 가져온 결과를 **DataStore 메서드로 저장**(중복은 DataStore가 판단). 소급 계산(fill_metrics 류)도 Fetcher가 fetch→DataStore.update.
- **DataView**: "티어 뷰"/"그룹 뷰" 단위로 구성원 데이터를 DataStore에서 받아 통계·재가공(평균 등락, 상승/하락 수, 정규화 시계열, 지표 시계열 등).
- **ChartDrawer**: DataView가 만든 가공 데이터를 입력받아 Chart.js로 렌더(가격/메트릭/복합/대시보드 차트).

---

## 3. 결정 사항 (확정/제안)

### 확정 (사용자 결정 완료)
- **Q1 → View=백엔드(Python) / ChartDrawer=프런트(JS)**.
  - ⇒ 현재 JS에 있던 **계산(정규화·robustY·PER floor·티어 집계)을 백엔드 DataView로 이동**. 프런트는 렌더만.
  - ⇒ **귀결(리뷰 시 확인)**: 정규화 토글·기간 변경 등은 DataView API를 다시 호출(서버 왕복). 현재 즉시 클라이언트 변환 대비 UX가 바뀜.
- **Q2 → `app/` 패키지로 오브젝트별 파일 분리**.
- **Q3 → 별도 컨트롤러 계층** (라우트와 오브젝트 사이 오케스트레이션).

### 확정 (2차 — 사용자 결정 완료)
- **Q4 → 상속 구조**: 공통 base `DataView`를 두고 **티어·그룹이 각각 이를 상속한 개별 오브젝트**.
  각 티어/그룹별 종속 메서드·attribute를 가질 수 있게 함.
  - *세부 확인 1건 남음* → 아래 "남은 확인" 참고(상속 단위).
- **Q5 → 데이터 vs 차트 경계 (제안 뒤집힘)**:
  - **차트를 그리기 위한 변환 = ChartDrawer(프런트)**: 정규화, robustY 축, PER floor(표시용 0처리), 색상, 호버, 툴팁, Y축 드래그.
    (정규화 등은 "차트로 보여주기 위한 목적 외에 의미가 없음")
  - **그 자체로 의미를 갖는 데이터·통계 = DataView(백엔드)**: PER·PBR·CAPEX·FCF·가격·등락률, 티어/그룹 통계(평균 등락·상승/하락 수 등).
  - ⇒ **귀결**: 정규화는 프런트 변환이므로 **토글 시 서버 왕복 없음**(1차 우려 해소).
- **Q6 → 진행 순서 유연**: 고정 순서 아님. 각 RF의 **의존성·영향도**를 보고 진행 순서를 그때 결정.

### 확정 (3차 — Q4 상속단위)
- **상속 계층**(전략적 선택 — 공통 로직 + 티어별 특수 목적 모두 대응, 추후 가지치기 용이):
```
DataView (base, 공통 재가공·통계)
├─ TierView (티어 공통 로직)
│   ├─ Tier1View / Tier2View / Tier3View (티어별 특수 목적)
└─ GroupView (그룹 로직, group id로 인스턴스 구분)
```

---

## 4. 실행 항목 (RF-xx)

> 의존성 순서대로. 각 항목은 독립 검증 가능하도록 쪼갬. 항목별로 진행 전 작업안을 보이고 컨펌받는다.

| ID | 오브젝트 | 내용 | 의존 | 위험 |
|----|----------|------|------|------|
| RF-00 | (기반) | `app/` 패키지 스캐폴드 + 모델/상수 이동(`database.py`→`app/models.py`, `app/constants.py`). 동작 동일. | - | 낮음 |
| RF-01 | DataStore | `app/store.py` 도입 — 스냅샷/메타/그룹 CRUD + **중복확인**을 클래스로. 기존 `db.query(...)`·`get_*`·`cleanup_*`를 위임. | RF-00 | 중간 |
| RF-02 | Fetcher | `app/fetcher.py` 도입 — yfinance(가격·재무)+네이버/야후 검색. **DataStore를 통해 저장·중복확인**. `collect_all`/`backfill_*`/`fill_*`/`search_*` 이전. | RF-01 | 중간 |
| RF-03 | DataView | `app/views.py` 도입 — `DataView`→`TierView`→`Tier1/2/3View`, `GroupView`(상속 계층). **그 자체로 의미 있는 데이터·통계**(메트릭 시계열, 티어/그룹 집계)를 JSON 제공. *정규화·robustY·PER floor는 차트 영역이라 제외.* | RF-01 | 높음 |
| RF-04 | Controller | `app/controllers.py` — 라우트와 오브젝트 사이 오케스트레이션. | RF-01~03 | 중간 |
| RF-05 | 라우트 | 라우트를 얇게 정리(`app/routes.py` 등), `main.py`는 부트스트랩만. | RF-04 | 중간 |
| RF-06 | ChartDrawer | 인라인 JS(`chart.html`/`index.html`)를 `static/js/`로 분리, **DataView JSON을 받아 렌더 + 차트용 변환(정규화·robustY·PER floor·색상·인터랙션)을 담당하는 ChartDrawer 오브젝트**로 재구성. | RF-03 | 높음 |

### 진행 현황
- **RF-00 ✅ 완료** — `app/` 스캐폴드, `database.py`→`app/models.py`, 상수→`app/constants.py`. 전 엔드포인트 200 검증.
- **RF-01 ✅ 완료** — `app/DataStore.py` 도입(스냅샷·로그·중복확인). 파일명=클래스명(`DataStore.py`).
- **RF-01b ✅ 완료** — 메타/그룹/그룹종목 CRUD를 DataStore로. 쓰기 라운드트립(그룹 생성→삭제) 검증.
- **RF-02 ✅ 완료** — `app/Fetcher.py` 도입(수집·백필·소급·검색). CC-07·CC-14 흡수, `collector.py` 삭제.
- **RF-03 ✅ 완료(confirm)** — `app/DataView.py`(DataView→TierView→Tier1/2/3View, GroupView, Catalog, MetricSeriesView). snap_to_dict·api_summary·index·api_stocks 이전, 대시보드 통계를 백엔드 SUMMARY로 이동. (2026-06-09 사용자 confirm)
  - **메트릭 시계열 이관 완료** — `api_history`가 main.py 인라인 dict 생성 → `MetricSeriesView(store, ticker, days).rows()` 경유. 단일 종목 시계열이라 DataView 상속 계층과 성격이 달라 Catalog처럼 독립 뷰로 둠. days 변환은 라우트 소관 유지. 기존 출력과 byte-identical 검증.
  - **잎 클래스(Tier1/2/3View·GroupView)는 의도적 보류** — 티어/그룹별 특수목적 확장 지점(scaffolding). 현재 라우트는 `TierView(store, t)`로 처리하며 잎 클래스 미인스턴스화. 사용자 합의된 '중간과정' 상태(결함 아님).
  - **하위: constants.py 삭제 + tier 비정규화 교정** — 아래 별도 섹션.
- **(계획 외) models.py 제거 🟢 구현 완료·confirm 대기** — `app/DataStore/` 패키지화(entities/db/store/__init__), 세션 완전 캡슐화(get_store/session), Fetcher(store), 라우트는 raw 세션 미노출. "DB는 DataStore를 통해서만 접근" 확립.

### RF-04 진행 (Controller 계층 — B안: 일관·transport독립·도메인분리)
> 방향 확정: 모든 라우트가 Controller 위임, Controller는 HTTP 무관(데이터 반환/도메인예외),
> 도메인별 분리(Collection/Dashboard/Stock/Group), RF-05(라우트 분리)와 함께.

- **S1 ✅ `app/errors.py`** — `AppError`(status) + `NotFoundError`(404)/`ConflictError`(409)/`ValidationError`(400). main.py에 단일 `@app.exception_handler(AppError)` 등록 → 라우트의 산재 `HTTPException` 제거 기반.
- **S2 ✅ `CollectionController` (시범)** — `app/controllers/`(패키지) + `CollectionController`(collect/reset/cleanup/fill_metrics/backfill). `collection_controller` Depends 팩토리로 요청단위 주입. 수집 5개 라우트를 위임으로 전환. 검증: 핸들러 등록·400/404 매핑·5라우트 주입·ValidationError 동작 확인.
- **S3 ✅ DashboardController** — index/api_stocks/api_summary/api_history/chart_page/groups_page. 페이지는 '템플릿 컨텍스트 dict'(dashboard/chart/groups_page_context), API는 데이터 반환. main.py에서 `json`·`AllView`·`TierView`·`MetricSeriesView`·`TIERS` dead import 제거(Catalog·TIER_GROUP은 잔존 라우트가 사용). 검증: stocks/summary/history byte-identical, 6라우트 주입 확인.
- **S4 ✅ StockController** — manage/add_stock/toggle_stock/ticker_info/search_ticker. `NotFoundError`(404) 첫 적용(toggle·ticker_info). ticker_info는 Catalog 직접 사용(`_all_known_stocks` 헬퍼는 잔존 group 라우트가 써서 S5까지 유지). 검증: manage_context·ticker_info 일치, 404 매핑, 5라우트 주입.
- **S5 ✅ GroupController** — 그룹 CRUD·멤버·fetch/fill·fix_kr_names (10라우트). `_all_known_stocks` 헬퍼 흡수(Catalog 직접). 스케줄러 `scheduled_collect`도 CollectionController 경유로 통일. main.py에서 `Fetcher`·`BACKFILL_PERIODS`·`Catalog`·`TIER_GROUP`·`HTTPException` 전부 제거. **검증**: list_groups byte-identical, 404/409/400 매핑, get_store 직접의존=팩토리 4개뿐, 데이터 라우트 26개 전부 controller 경유.
  - ⚠️ **동작 변경 1건(의도)**: `create_group` 중복명이 `HTTPException(400)` → `ConflictError(409)`. 본문 형식(`{"detail": msg}`)은 동일, 프런트는 non-2xx 동일 처리. 400 유지 원하면 `ConflictError`→`ValidationError`로 전환 가능.
- **S6 ✅ (RF-05) 라우트 분리** — `app/routes/`(dashboard/collection/stock/group APIRouter) + `app/templating.py`(공유 templates). 컨트롤러 팩토리·PERIOD_TO_DAYS를 각 라우터로 이동. main.py는 **부트스트랩만**(app 생성·마운트·예외핸들러·스케줄러·시드·include_router) — 라우트 핸들러 0개, 정의 함수=app_error_handler/lifespan/scheduled_collect/seed_stock_meta. **검증**: 27라우트 인벤토리 원본과 동일, 정적/파라미터 충돌(`/api/groups/fill-metrics` vs `{group_id}`) 올바른 엔드포인트 라우팅, import OK.

### RF-06 진행 (ChartDrawer — 프런트 인라인 JS 분리 + 차트 오브젝트)
> 경계(Q5): ChartDrawer=차트 렌더+변환(정규화·robustY·PER floor·색상·툴팁·호버·Y축),
> 나머지(선택상태·fetch·테이블·액션)=페이지 글루. 검증은 시각/수동(node 구문 + 브라우저).

- **R1 ✅ `static/js/toast.js` 공용화** — 4개 템플릿(index/chart/manage/groups)에 중복이던 `showToast` 제거, 단일 파일로. 외부 JS 분리·`/static/js/` 서빙 패턴 확립(부트 패턴 준비). timeout 3500/3000 혼재 → 3000 통일, 기본 `cls="ok"`. **검증**: node 구문 OK, 앱 기동해 5페이지 200·toast.js 서빙 200·showToast 호출 보존 확인.
- **R2 ✅ `ChartDrawer.js` (렌더 툴킷)** — 코드 정독 결과 차트 팩토리(updateChart/drawMetricChart/drawCombinedChart)는 DOM·전역상태(selectedTickers/cache/chart)와 깊게 결합 → **통째 이동은 대규모 재작성+시각검증** 위험. 따라서 **깨끗이 분리 가능한 렌더 툴킷만** ChartDrawer로: 테마(THEME)·팔레트/색상(color/name, init(stocks))·축(xScale/yScale)·툴팁(tooltip)·robustYRange. chart.html은 `ChartDrawer.init(ALL_STOCKS)` 후 `ChartDrawer.*` 호출(색상5·툴팁3·축6·robustY1·name3·테마3·팔레트2). **검증**: ChartDrawer.js·chart.html 인라인 JS node 구문 OK, 구 이름 잔존0/이중치환0, /chart 200·ChartDrawer.js 서빙 200·타 페이지 회귀 없음. ⚠️ **시각 렌더·인터랙션(정규화 토글·지표차트·Y축드래그·호버)은 브라우저 수동 확인 필요**(자동검증 불가).
  - **경계 재정의**: ChartDrawer=순수 렌더 툴킷(상태·DOM 무관). 차트 팩토리는 DOM/상태 결합이라 **페이지 글루(chart-page.js, R3)** 소관으로 — 원래 R2 범위에서 팩토리를 R3로 이관.
- **R3 ✅ `chart-page.js`** — chart.html 인라인 JS(~1035줄) 전체를 `static/js/chart-page.js`로 분리(선택상태·fetch·사이드바·컨트롤 + 차트 팩토리 + 플러그인/호버/Y축). 종목/그룹 데이터는 템플릿이 `window.BOOT`로 주입, chart-page.js가 읽음. 로드순서: Chart.js→toast→ChartDrawer→BOOT→chart-page. chart.html **1366→331줄**(마크업+부트+script태그만). onclick 핸들러 12곳은 전역함수 그대로 동작(외부 classic 스크립트=전역 스코프). **검증**: chart-page.js node 구문 OK, /chart 200·chart-page.js 서빙 200·window.BOOT(43종목·1그룹) 주입·타 페이지 회귀 없음. ⚠️ 시각 인터랙션은 브라우저 수동 확인.
- **R4 ✅ `dashboard-page.js`** — index.html 인라인 JS를 `static/js/dashboard-page.js`로 분리(테이블 필터·정렬·요약·요약차트·액션 트리거). 데이터는 `window.BOOT`(stocks/summary) 주입. 요약차트(tierChart/distChart) 축 테마색을 `ChartDrawer.THEME`(tick/gridX/grid, 값 동일 1:1)로 공유 — stepSize/커스텀 축은 위험 대비 실익 적어 유지. index.html **475→226줄**. 로드순서 Chart.js→toast→ChartDrawer→BOOT→dashboard-page. **검증**: node 구문 OK, / 200·dashboard-page.js 서빙 200·window.BOOT(43종목·summary 3키) 주입·타 페이지 회귀 없음.

**→ RF-06 완료. 사용자 정의 4 오브젝트(DataStore·Fetcher·DataView·ChartDrawer) 모두 구현. RF-01~06 전체 완결.**
> ChartDrawer는 '렌더 툴킷(테마·색상·축·툴팁·robustY, 양 페이지 공유)'으로 실현. 차트 팩토리는 DOM/상태 결합이라 페이지 글루(chart-page.js)에 둠 — 원안의 "팩토리=ChartDrawer"에서 경계를 조정한 형태.
- **R4 ⬜ `dashboard-page.js`** — index.html 분리 + 요약차트를 ChartDrawer로.

### 운영 편의 (2026-06)
- **EX-05 ✅ 기동 시 공백 메움 동기화 + 전 종목 포함** — lifespan에서 `startup_sync`를 `date` 트리거로 **기동 직후 1회 백그라운드 실행**(논블로킹, 9/18 cron=collect만 유지).
  - **전 종목**: `collect_all` 대상을 `active_metas`(마스터) + **GroupStock(그룹 전용)**까지 확장. 그룹은 `SimpleNamespace(sector=None)`로 래핑해 동일 경로 통과. (ETF 그룹종목은 재무 없어 PER/PBR=None, 가격만 — 정상)
  - **무조건 공백 메움**: `sync_to_today()` = `collect_all()`(오늘, 시총·52주·네이버 KR) → `_gap_period()`로 gap 산정(가장 뒤처진 종목 기준 최소 period) → `backfill_all`(마스터)+`backfill_group_stocks`(그룹)로 **마지막 데이터~오늘 빠진 거래일 전부 채움**(중복 스킵). 단순 "오늘 1개"가 아니라 서버 꺼진 동안의 공백을 모두 보충.
  - **성능**: `backfill_all`에 "새 날짜 없으면 재무조회 생략" 최적화 → 공백 없을 때 빠른 통과(43종목 sync ~7초, 재무조회 0건). 공백 클 때만 해당 종목 재무 조회.
  - **검증**: 논블로킹 기동, sync 전체 흐름(수집→gap 산정→백필→완료) 로그 무에러, gap=4일→period 5d, 대상 41→43, SimpleNamespace end-to-end(sector=None) 확인.

### 추가 작업 (2026-06 · RF 외 — 캡슐화·정확성·데이터소스)
> 계획서 RF/CC 어디에도 없던, 별도 세션에서 진행한 작업. 추적용 기록.

- **EX-01 ✅ DataStore 완전 캡슐화 (DTO 도입)** — 읽기 메서드가 살아있는 ORM 엔티티 대신 **불변 DTO(frozen dataclass: Snapshot/Meta/GroupStock/Group/Member/Log)** 반환. 내부 쓰기용 `_meta_entity`/`_group_entity` 분리, `update_snapshot_metrics` 신설. "외부에서 DB 변경은 DataStore 쓰기 메서드로만"을 **구조적으로 강제**(변이 시 FrozenInstanceError). 컬럼명 미러링으로 소비 코드 무수정.
- **EX-02 ✅ `(ticker, collected_at)` 복합 인덱스** — `latest_snapshots`/`price_history`/`latest_snapshot_date`가 커버링 인덱스 사용. 203k행에서 latest_snapshots ~34ms→~11ms, price_history 정렬 TEMP B-TREE 제거. init_db 멱등 마이그레이션.
- **EX-03 ✅ 지표 방법론 통일 (버그 수정)** — 일일수집·백필·소급의 PER/PBR/CAPEX/FCF/payout 계산을 단일 규칙으로:
  - **payout 버그**: collect_all이 (분기 배당+자사주)÷**TTM 순이익**으로 기간 불일치(~1/4 과소) → **분기 순이익** 기준으로 교정.
  - **PER/PBR**: collect_all의 야후 `trailingPE`/`priceToBook`(시점값) → 백필과 동일한 **가격÷TTM EPS·가격÷BPS**(계산값)로 통일 → 시계열 단차 제거.
  - collect_all CF 인라인 파싱 제거 → `_quarterly_fundamentals` 단일 경로. 죽은 헬퍼 `_latest_cf_value` 삭제.
  - ⚠️ **이미 저장된 과거 일일수집 행은 구 방식 값 잔존** → reset 후 재백필 필요(별도 안내).
- **EX-04 ✅ KR 가격 소스 네이버 전환** — 야후 `.KS` 일별 종가 지연(예: 06-04 Close=NaN, 거래량만 존재)으로 일일수집이 최신일을 스킵하던 문제 해결. `collect_all`을 `_collect_us`(yfinance 일괄)·`_collect_kr_one`(네이버 `api/stock/{code}/price`)로 분리, 스냅샷 저장·지표계산은 공용 `_store_snapshot`으로 DRY화. KR은 거래일 noon UTC로 datestamp(백필과 일관). **재무지표(PER/PBR/CAPEX/FCF/payout)는 양쪽 다 야후 분기재무 동일 규칙** — 가격 출처만 분기. 실측: 000660/247540 네이버에서 당일 종가 수신, 06-09 정상 저장 확인. **단, 백필(`backfill_*`)은 야후 유지** — 일별 최신만 문제였고 과거 시계열은 야후로 충분(추후 필요 시 네이버 전환 검토).

### RF-03 하위: constants.py 삭제 + tier 비정규화 교정
**근본 원인**: `stock_snapshots.tier`가 non-null로 비정규화되어 ① Fetcher가 분류(tier)를 떠안고 ② 그룹 종목에 "그룹" 필러(2,420행) ③ TIERS/TIER_GROUP이 흩어짐.

**증거**: tier 컬럼은 value-agnostic(String, 제약 없음), DataStore는 tier 값 미참조 → tier 분류는 **DataView 소유**가 맞음.

**소유 결론**:
- TIERS·TIER_GROUP → **DataView**
- BACKFILL_PERIODS → **Fetcher**
- PERIOD_TO_DAYS → **라우트(차트 기간 어휘)**

**작업 (🟢 구현 완료·confirm 대기)**:
1. ✅ DataView가 tier 도출 — `tier_of(ticker)`: 마스터=StockMeta.tier(active_metas injection), 그룹 전용=TIER_GROUP. `to_dict`가 도출값 출력 → 프런트 JSON 불변
2. ✅ `stock_snapshots.tier` 컬럼 **DROP**(SQLite 3.53, init_db 마이그레이션). 다른 데이터 보존
3. ✅ Fetcher가 tier 미작성 — `meta.tier` 복사·`TIER_GROUP` 삭제 → **Fetcher의 tier/TIER_GROUP 의존 0**
4. ✅ 상수 분산: TIERS·TIER_GROUP→DataView, BACKFILL_PERIODS→Fetcher, PERIOD_TO_DAYS→main.py. **constants.py 삭제**

**검증**: tier 도출 분포 {1차:18, 2차:17, 3차:6, 그룹:2} = 기존 저장값과 일치, TierView(1차)=18, 전 엔드포인트 200, `stock_snapshots`에 tier 컬럼 없음.

### 주의 (의존 결합)
- **RF-03 ↔ RF-06**: DataView가 제공하는 데이터·통계 **JSON 스키마**를 ChartDrawer와 먼저 합의해야 함. 단, 정규화 등 차트 변환은 프런트에 남으므로 결합도는 (1차 우려보다) 낮음.
- 각 RF는 완료 시 기존 동작(엔드포인트·차트)이 동일하게 유지되는지 검증 후 진행.
- **진행 순서는 고정 아님** — 의존성·영향도에 따라 선택.

---

## 5. 목표 디렉토리 구조 (제안)
```
app/
  __init__.py
  models.py        # 모델 + engine/session + init_db (기존 database.py)
  constants.py     # TIERS, TIER_GROUP, PERIOD_TO_DAYS, BACKFILL_PERIODS, yfinance 키
  DataStore.py     # DataStore
  Fetcher.py       # Fetcher (yfinance/naver)
  DataView.py      # DataView (TierView/GroupView)
  Controller.py    # Controller (오케스트레이션)
  routes.py        # FastAPI 라우트 (얇게)
main.py            # 앱 부트스트랩(생성·라우트 등록·스케줄러·lifespan)
static/js/
  ChartDrawer.js   # ChartDrawer
  ...              # 기존 인라인 JS 이전
templates/*.html   # script src로 외부 JS 참조
```
> **명명 규칙: 파일명 = 클래스명(정확 일치)** — `DataStore.py`, `Fetcher.py`, `DataView.py`, `Controller.py`, `ChartDrawer.js`. 구조는 리뷰 시 조정 가능.
