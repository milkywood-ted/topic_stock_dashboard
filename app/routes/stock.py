"""종목 마스터 관리·조회·검색 라우트."""
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, JSONResponse

from app.DataStore import DataStore, get_store
from app.controllers import StockController
from app.templating import templates

router = APIRouter()


def stock_controller(store: DataStore = Depends(get_store)) -> StockController:
    return StockController(store)


@router.get("/api/search-ticker")
async def search_ticker(q: str, ctrl: StockController = Depends(stock_controller)):
    """Yahoo Finance + 네이버 금융으로 종목명·티커 검색"""
    return ctrl.search(q)


@router.get("/api/ticker-info/{ticker}")
async def ticker_info(ticker: str, ctrl: StockController = Depends(stock_controller)):
    """종목 기본 정보 조회 — 한국 종목은 네이버 우선, 없으면 Yahoo"""
    return ctrl.ticker_info(ticker)


@router.get("/manage", response_class=HTMLResponse)
async def manage(request: Request, ctrl: StockController = Depends(stock_controller)):
    return templates.TemplateResponse(
        request=request, name="manage.html",
        context={"request": request, **ctrl.manage_context()},
    )


@router.post("/manage/add")
async def add_stock(
    ticker: str = Form(...),
    name:   str = Form(...),
    tier:   str = Form(...),
    sector: str = Form(""),
    market: str = Form("US"),
    ctrl: StockController = Depends(stock_controller),
):
    return JSONResponse(ctrl.add_stock(ticker, name, tier, sector, market))


@router.post("/manage/toggle/{ticker}")
async def toggle_stock(ticker: str, ctrl: StockController = Depends(stock_controller)):
    return ctrl.toggle_stock(ticker)
