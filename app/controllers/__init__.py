"""Controller 계층 — 라우트와 오브젝트(DataStore/Fetcher/DataView) 사이 오케스트레이션.

Controller는 transport(HTTP)를 모른다: 순수 파라미터를 받아 데이터/DTO를 반환하거나
app.errors 도메인 예외를 raise한다. HTTP 변환은 라우트와 예외 핸들러 소관.
도메인별로 분리한다(Collection/Dashboard/Stock/Group).
"""
from app.controllers.CollectionController import CollectionController
from app.controllers.DashboardController import DashboardController
from app.controllers.StockController import StockController
from app.controllers.GroupController import GroupController

__all__ = ["CollectionController", "DashboardController", "StockController", "GroupController"]
