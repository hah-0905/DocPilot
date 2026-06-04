class AppException(Exception):
    def __init__(
        self,
        message: str,
        code: int = 400,
        status_code: int = 400,
        data: object | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        self.data = data
        super().__init__(message)