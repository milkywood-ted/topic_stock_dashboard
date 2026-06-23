"""사용자 그룹·구성원·그룹종목 데이터 라우트."""
from fastapi import APIRouter, Depends, Form
from fastapi.responses import JSONResponse

from app.DataStore import DataStore, get_store
from app.controllers import GroupController

router = APIRouter()


def group_controller(store: DataStore = Depends(get_store)) -> GroupController:
    return GroupController(store)


@router.post("/api/fix-kr-names")
async def fix_kr_names(ctrl: GroupController = Depends(group_controller)):
    """GroupStock 내 한국 종목의 이름을 네이버 한국어로 일괄 수정"""
    return ctrl.fix_kr_names()


@router.get("/api/groups")
async def api_groups(ctrl: GroupController = Depends(group_controller)):
    return ctrl.list_groups()


@router.post("/api/groups")
async def create_group(name: str = Form(...), note: str = Form(""),
                       ctrl: GroupController = Depends(group_controller)):
    return ctrl.create_group(name, note)


@router.delete("/api/groups/{group_id}")
async def delete_group(group_id: int, ctrl: GroupController = Depends(group_controller)):
    return ctrl.delete_group(group_id)


@router.post("/api/groups/{group_id}/members")
async def add_member(
    group_id: int,
    ticker: str = Form(...),
    name:   str = Form(""),
    market: str = Form("US"),
    ctrl: GroupController = Depends(group_controller),
):
    return ctrl.add_member(group_id, ticker, name, market)


@router.post("/api/groups/fill-metrics")
async def fill_all_group_metrics(ctrl: GroupController = Depends(group_controller)):
    """전체 그룹 종목 PER/PBR/CAPEX/FCF 소급"""
    return JSONResponse(ctrl.fill_metrics(group_id=None))


@router.post("/api/groups/{group_id}/fill-metrics")
async def fill_one_group_metrics(group_id: int, ctrl: GroupController = Depends(group_controller)):
    """특정 그룹 종목 PER/PBR/CAPEX/FCF 소급"""
    return JSONResponse(ctrl.fill_metrics(group_id=group_id))


@router.post("/api/groups/{group_id}/fetch-data")
async def fetch_group_data(
    group_id: int,
    period: str = Form("1y"),
    ctrl: GroupController = Depends(group_controller),
):
    """그룹 내 전체 종목 데이터 수집"""
    return JSONResponse(ctrl.fetch_data(group_id, period))


@router.delete("/api/groups/{group_id}/members/{ticker}")
async def remove_member(group_id: int, ticker: str, ctrl: GroupController = Depends(group_controller)):
    return ctrl.remove_member(group_id, ticker)


@router.patch("/api/groups/{group_id}")
async def rename_group(group_id: int, name: str = Form(...), note: str = Form(""),
                      ctrl: GroupController = Depends(group_controller)):
    return ctrl.rename_group(group_id, name, note)
