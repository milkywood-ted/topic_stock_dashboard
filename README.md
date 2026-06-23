# AI 수혜 종목 트래커

AI 1차·2차·3차 수혜 기업의 주가·지표를 자동 수집하여  
웹 대시보드로 시각화하는 Python 앱입니다.

## 기술 스택
- **Backend**: FastAPI + SQLite (SQLAlchemy)
- **데이터 수집**: yfinance (주가·재무) + 네이버 증권 검색 (한국 종목명)
- **자동 스케줄**: APScheduler (매일 09:00 / 18:00 UTC)
- **Frontend**: 순수 HTML/CSS/JS + Chart.js

## 설치 및 실행

```bash
# 1. 패키지 설치
pip install -r requirements.txt

# 2. 서버 시작
python main.py

# 3. 브라우저에서 접속
# http://localhost:8000
```

## 기능

### 대시보드 (`/`)
- 전체 종목 요약 카드 (상승/하락/보합 수)
- 티어별 평균 등락률 바차트
- 등락률 분포 히스토그램
- 종목 테이블 (필터·검색·정렬)
- "지금 수집" 버튼으로 수동 갱신

### 멀티 차트 (`/chart`)
- 여러 종목 가격 추이 비교 (절대가격·정규화 %)
- 기간 선택(1주~전체), Y축 수동 조정·스크롤 줌
- PER · PBR · FCF · (CAPEX+주주환원율) 보조 지표 차트 토글
- 사이드바에서 티어·내 그룹별 선택

### 종목 관리 (`/manage`)
- 종목 추가 / 활성화·비활성화
- 수집 이력 확인 (성공/실패 로그)

### 그룹 관리 (`/groups`)
- 나만의 종목 그룹 생성·삭제
- 종목 검색(영문 Yahoo / 한글 네이버) 후 그룹에 추가
- 그룹 전용 종목은 별도 수집(`group_stocks`), 기간별 과거 데이터·지표 소급

### 용어 사전 (`/glossary`)
- PER·PBR·CAPEX·FCF 등 지표 설명 (검색·목차)

### API 엔드포인트 (주요)
| 경로 | 설명 |
|------|------|
| `GET /api/stocks` | 전체 종목 최신 데이터 (JSON) |
| `GET /api/history/{ticker}?period=3mo` | 특정 종목 가격·지표 이력 |
| `GET /api/summary` | 티어별 요약 통계 |
| `GET /api/search-ticker?q=...` | 종목명·티커 검색 (Yahoo + 네이버) |
| `GET /api/groups` | 그룹·구성 종목 목록 |
| `POST /collect` | 수동 수집 트리거 |
| `POST /backfill?period=1y` | 과거 데이터 일괄 수집 |
| `POST /fill-metrics` | PER/PBR/CAPEX/FCF 소급 계산 |

## 데이터베이스

`data/ai_stocks.db` (SQLite)

- `stock_meta` : 종목 마스터 (추가·삭제 가능)
- `stock_snapshots` : 수집된 주가·지표 스냅샷 (이력 누적)
- `collect_logs` : 수집 이력
- `user_groups` / `group_members` : 사용자 정의 그룹과 구성 종목
- `group_stocks` : 그룹 전용 종목 (마스터에 없는 종목)

## 향후 확장 (2단계: 외부 서버 배포)

```bash
# PostgreSQL로 마이그레이션
DATABASE_URL="postgresql://user:pw@host/dbname"

# Docker 컨테이너화
docker build -t ai-tracker .
docker run -p 8000:8000 ai-tracker

# Nginx 리버스 프록시 + SSL 설정
# → 외부 접속 가능한 도메인 연결
```

## 주의사항
- yfinance는 Yahoo Finance 비공식 API 기반으로,
  간헐적으로 요청 제한이 걸릴 수 있습니다.
- 한국 종목 티커: `005930.KS` 형식 사용
- 수집 주기를 너무 짧게 설정하면 IP 차단 위험 있음
  (최소 30분 간격 권장)
