from fastapi import HTTPException


def api_error(status_code: int, code: str, message: str, **details: object) -> HTTPException:
    payload = {"code": code, "message": message, **details}
    return HTTPException(status_code=status_code, detail={"error": payload})
