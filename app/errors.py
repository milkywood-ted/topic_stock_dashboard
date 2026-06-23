"""도메인 예외 — Controller가 raise, 라우트(예외 핸들러)가 HTTP로 변환.

Controller는 HTTP를 모른다. 실패는 이 예외들로 표현하고, main.py에 등록한
단일 핸들러가 status 코드로 매핑한다 (라우트의 산재한 HTTPException 제거).
"""


class AppError(Exception):
    """도메인 오류 기반 클래스. status는 HTTP 매핑용 힌트."""
    status = 400

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class NotFoundError(AppError):
    """대상 리소스 없음 → 404."""
    status = 404


class ConflictError(AppError):
    """상태 충돌(중복 등) → 409."""
    status = 409


class ValidationError(AppError):
    """입력 검증 실패 → 400."""
    status = 400
