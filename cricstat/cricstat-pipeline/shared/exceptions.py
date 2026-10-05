"""Custom exceptions. The CLI maps them to exit codes (see presentation-logic/cli)."""


class PipelineError(Exception):
    """Base exception for cricstat-pipeline. Exit code 1."""


class DownloadError(PipelineError):
    """A Cricsheet download failed after every retry."""


class SourceError(PipelineError):
    """The source zip is missing, unreadable or not a zip."""


class DataQualityError(PipelineError):
    """A data-quality gate failed. The run was rolled back. Exit code 2."""

    def __init__(self, message, failures=None):
        super().__init__(message)
        self.failures = list(failures or [message])
