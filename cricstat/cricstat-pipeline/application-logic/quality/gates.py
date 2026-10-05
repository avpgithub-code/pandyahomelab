"""Data-quality gates, evaluated BEFORE the ingest transaction commits.

Pure functions over run counts: no SQL, no I/O. A non-empty result fails the run,
which the service then rolls back (exit code 2).
"""
from typing import List


def failed_threshold(json_files: int, max_abs: int, max_frac: float) -> int:
    """Largest tolerated number of unparseable files: max(max_abs, max_frac * files)."""
    return max(max_abs, int(max_frac * json_files))


def evaluate(mode: str, json_files: int, failed: int, active_before: int, active_after: int,
             max_failed_abs: int = 5, max_failed_frac: float = 0.005,
             max_active_drop_frac: float = 0.02) -> List[str]:
    """Return the list of gate failures (empty = pass)."""
    failures = []
    if mode == "full" and json_files == 0:
        failures.append("full download contains no match files")
    limit = failed_threshold(json_files, max_failed_abs, max_failed_frac)
    if failed > limit:
        failures.append("%d files failed to parse (limit %d of %d)" % (failed, limit, json_files))
    if mode == "full" and active_before > 0:
        floor = active_before * (1 - max_active_drop_frac)
        if active_after < floor:
            failures.append(
                "active matches would drop from %d to %d (more than %.1f%%)"
                % (active_before, active_after, 100 * max_active_drop_frac))
    return failures
