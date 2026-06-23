"""FastAPI 라우터 — 도메인별 분리 (dashboard/collection/stock/group).

각 라우터는 얇은 어댑터: 요청 파싱 → Controller 위임 → 응답/템플릿 변환.
오케스트레이션은 Controller, HTTP 매핑은 라우터+예외 핸들러 소관.
"""
