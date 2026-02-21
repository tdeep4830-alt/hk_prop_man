"""Application-level exceptions with i18n support."""


class AppException(Exception):
    """Raise this from any service/endpoint for automatic multilingual error responses.

    Usage::

        raise AppException(409, "auth.email_exists")
        raise AppException(429, "auth.quota_exceeded", limit=10)
    """

    def __init__(self, status_code: int, i18n_key: str, **fmt_args: object) -> None:
        self.status_code = status_code
        self.i18n_key = i18n_key
        self.fmt_args = fmt_args
        super().__init__(i18n_key)
