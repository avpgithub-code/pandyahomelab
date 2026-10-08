"""Custom exceptions. The CLI maps them to exit codes (see presentation-logic/cli)."""


class ModelsError(Exception):
    """Base exception for cricstat-models. Exit code 1."""


class SourceError(ModelsError):
    """A Wikipedia request failed after every retry, or a page could not be parsed."""


class DataCheckError(ModelsError):
    """A data check failed (supplement, crosswalks, tournament configs). Exit code 2:
    nothing downstream runs and the previous forecast stays live."""
