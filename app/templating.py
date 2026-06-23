"""공유 Jinja2 템플릿 — 페이지 라우터들이 import해서 사용.

directory는 프로젝트 루트 기준 상대경로(앱은 루트에서 구동).
"""
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")
