"""Errors the HTTP layer turns into application/problem+json (RFC 9457, F5 §2)."""


class ApiError(Exception):
    status = 500
    title = "Internal error"

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class BadFilter(ApiError):
    status, title = 400, "Bad filter"


class NotFound(ApiError):
    status, title = 404, "Not found"


class Incompatible(ApiError):
    status, title = 422, "Filters that can't combine"


class NoData(ApiError):
    status, title = 503, "Serving database unavailable"
