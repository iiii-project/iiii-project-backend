from rest_framework.exceptions import APIException


class DomainError(APIException):
    status_code = 400
    default_code = "INVALID_REQUEST"

    def __init__(self, code: str, message: str, status_code: int = 400):
        self.status_code = status_code
        self.detail = message
        self.default_code = code
