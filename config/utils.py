from rest_framework.views import exception_handler


def ok(data=None, message: str = "操作成功") -> dict:
    return {"success": True, "data": data or {}, "message": message}


def fail(code: str, message: str, details=None) -> dict:
    return {"success": False, "error": {"code": code, "message": message, "details": details}}


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response

    detail = response.data
    message = detail.get("detail") if isinstance(detail, dict) else str(detail)
    code = getattr(exc, "default_code", "INVALID_REQUEST")
    response.data = fail(str(code).upper(), message or "請求無法處理", detail)
    return response
