"""Resolve the source zip for a mode (download or local --zip-path), then ingest it."""
import os
from typing import Optional

from application_logic.services.ingest_service import ingest_zip
from db_logic.loaders import downloader
from shared.config import Config
from shared.logger import get_logger

log = get_logger("refresh")


def run(mode: str, cfg: Config, zip_path: Optional[str] = None, download_fn=None):
    """Download (unless zip_path is given), ingest, prune old dated copies."""
    meta = {}
    if zip_path:
        zip_path = os.path.abspath(zip_path)
        source = zip_path
        log.info("%s run from local zip %s", mode, zip_path)
    else:
        url = cfg.FULL_URL if mode == "full" else cfg.RECENT_URL
        fetch = download_fn or downloader.download
        zip_path = fetch(url, cfg.RAW_ZIP_DIR, cfg.USER_AGENT, timeout=cfg.HTTP_TIMEOUT,
                         retries=cfg.HTTP_RETRIES, backoff=cfg.HTTP_BACKOFF, meta=meta)
        source = url
    summary = ingest_zip(cfg.RAW_DB, zip_path, mode, source=source,
                         max_failed_abs=cfg.MAX_FAILED_ABS,
                         max_failed_frac=cfg.MAX_FAILED_FRAC,
                         max_active_drop_frac=cfg.MAX_ACTIVE_DROP_FRAC,
                         source_last_modified=meta.get("last_modified"))
    summary["zip_path"] = zip_path
    if source != zip_path:
        keep = cfg.KEEP_FULL_ZIPS if mode == "full" else cfg.KEEP_RECENT_ZIPS
        for path in downloader.prune(cfg.RAW_ZIP_DIR, source, keep):
            log.info("pruned old download %s", path)
    return summary
