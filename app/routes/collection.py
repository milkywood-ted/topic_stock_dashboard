"""데이터 적재(수집·백필·소급·정리) 라우트."""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.DataStore import DataStore, get_store
from app.controllers import CollectionController

router = APIRouter()


def collection_controller(store: DataStore = Depends(get_store)) -> CollectionController:
    return CollectionController(store)


@router.post("/collect")
async def manual_collect(ctrl: CollectionController = Depends(collection_controller)):
    """수동 수집 트리거"""
    return JSONResponse(ctrl.collect())


@router.post("/reset-snapshots")
async def reset_snapshots(ctrl: CollectionController = Depends(collection_controller)):
    """스냅샷·수집 로그 전체 삭제 (종목 목록은 유지)"""
    return JSONResponse(ctrl.reset_snapshots())


@router.post("/cleanup-duplicates")
async def manual_cleanup(ctrl: CollectionController = Depends(collection_controller)):
    """중복 스냅샷 일괄 제거"""
    return JSONResponse(ctrl.cleanup_duplicates())


@router.post("/fill-metrics")
async def manual_fill_metrics(ctrl: CollectionController = Depends(collection_controller)):
    """기존 스냅샷에 PER/PBR/CAPEX/FCF 소급 적용"""
    return JSONResponse(ctrl.fill_metrics())


@router.post("/backfill")
async def manual_backfill(period: str = "1y",
                          ctrl: CollectionController = Depends(collection_controller)):
    """과거 데이터 일괄 수집"""
    return JSONResponse(ctrl.backfill(period))
