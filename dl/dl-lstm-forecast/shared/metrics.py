"""Metrics and monitoring."""


class Metrics:
    """Application metrics."""

    def __init__(self):
        self.predictions_total = 0
        self.predictions_errors = 0
        self.inference_time_ms = 0.0

    def record_prediction(self, success: bool, inference_time_ms: float):
        """Record prediction metrics."""
        self.predictions_total += 1
        if not success:
            self.predictions_errors += 1
        self.inference_time_ms = inference_time_ms
