"""대시보드·차트·종목목록·용어 페이지 라우트."""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse

from app.DataStore import DataStore, get_store
from app.controllers import DashboardController
from app.templating import templates

# 차트 조회 기간(api_history) → 일수 (라우트 소관)
PERIOD_TO_DAYS = {
    "1w": 7, "2w": 14, "1mo": 30, "3mo": 90, "6mo": 180,
    "1y": 365, "2y": 730, "5y": 1825, "max": 36500,  # max ≈ 100년(사실상 전체)
}

router = APIRouter()


def dashboard_controller(store: DataStore = Depends(get_store)) -> DashboardController:
    return DashboardController(store)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, ctrl: DashboardController = Depends(dashboard_controller)):
    return templates.TemplateResponse(
        request=request, name="index.html",
        context={"request": request, **ctrl.dashboard_context()},
    )


@router.get("/api/stocks")
async def api_stocks(ctrl: DashboardController = Depends(dashboard_controller)):
    return ctrl.stocks()


@router.get("/api/history/{ticker}")
async def api_history(ticker: str, period: str = "3mo",
                      ctrl: DashboardController = Depends(dashboard_controller)):
    days = PERIOD_TO_DAYS.get(period, 90)   # 기간 어휘→일수는 라우트 소관
    return ctrl.history(ticker, days)


@router.get("/api/summary")
async def api_summary(ctrl: DashboardController = Depends(dashboard_controller)):
    """티어별 요약 통계"""
    return ctrl.summary()


@router.get("/groups", response_class=HTMLResponse)
async def groups_page(request: Request, ctrl: DashboardController = Depends(dashboard_controller)):
    return templates.TemplateResponse(request=request, name="groups.html",
        context={"request": request, **ctrl.groups_page_context()})


@router.get("/chart", response_class=HTMLResponse)
async def chart_page(request: Request, ctrl: DashboardController = Depends(dashboard_controller)):
    return templates.TemplateResponse(
        request=request, name="chart.html",
        context={"request": request, **ctrl.chart_context()},
    )


@router.get("/glossary", response_class=HTMLResponse)
async def glossary(request: Request):
    return templates.TemplateResponse(request=request, name="glossary.html", context={"request": request})
