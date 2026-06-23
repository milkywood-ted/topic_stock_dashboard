"""
AI 수혜 종목 트래커 - FastAPI 부트스트랩
실행: python main.py
접속: http://localhost:8000

앱 생성·정적 마운트·예외 핸들러·스케줄러·시드만 담당.
라우트는 app/routes/(도메인별 APIRouter), 오케스트레이션은 app/controllers/.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler

from app.DataStore import init_db, session
from app.controllers import CollectionController
from app.errors import AppError
from app.routes import dashboard, collection, stock, group
from seed_data import INITIAL_STOCKS

# ── 스케줄러 ───────────────────────────────────────────────
scheduler = BackgroundScheduler()


def scheduled_collect():
    with session() as store:
        CollectionController(store).collect()


def startup_sync():
    """기동 시 1회 — 서버가 꺼져 있던 동안의 빠진 거래일까지 메움."""
    with session() as store:
        CollectionController(store).sync()


def seed_stock_meta():
    """최초 실행 시 종목 마스터 데이터 삽입"""
    with session() as store:
        if store.meta_count() == 0:
            store.seed_metas(INITIAL_STOCKS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시 DB 초기화 + 마스터 데이터 시드
    init_db()
    seed_stock_meta()

    # 매일 오전 9시 / 오후 6시 자동 수집 (평일 기준)
    scheduler.add_job(scheduled_collect, "cron", hour="9,18", minute=0,
                      id="auto_collect", replace_existing=True)
    scheduler.start()

    # 서버가 꺼져 있던 동안의 공백 보충 — 기동 직후 1회 백그라운드 동기화.
    # date 트리거(run_date 미지정=현재시각) → 스케줄러 스레드에서 즉시 실행되어
    # 서버 시작을 막지 않는다. sync_to_today가 오늘 수집 + 빠진 과거일 backfill로
    # 마지막 데이터~현재까지 공백을 모두 메운다(중복은 스킵).
    scheduler.add_job(startup_sync, "date", id="startup_sync",
                      replace_existing=True, misfire_grace_time=60)

    yield
    scheduler.shutdown()


app = FastAPI(title="AI 수혜 종목 트래커", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/knowledge", StaticFiles(directory="knowledge_document"), name="knowledge")


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    """도메인 예외 → HTTP. Controller는 HTTP를 모르고 이 핸들러가 status로 매핑."""
    return JSONResponse({"detail": exc.message}, status_code=exc.status)


app.include_router(dashboard.router)
app.include_router(collection.router)
app.include_router(stock.router)
app.include_router(group.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
