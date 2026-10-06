"""Download a Cricsheet file: descriptive User-Agent, timeouts, retry with backoff,
write to a .part file, validate it (a zip by default; the Register CSVs pass their own check),
then rename to a dated copy in data/raw/.
"""
import os
import time
import urllib.error
import urllib.request
import zipfile
from typing import Callable, List, Optional

from shared.exceptions import DownloadError
from shared.logger import get_logger

log = get_logger("downloader")
_CHUNK = 1 << 20


def dated_name(url: str, stamp: Optional[str] = None) -> str:
    """all_json.zip -> all_json-20261005.zip (UTC date)."""
    base = os.path.basename(url.split("?", 1)[0]) or "download.zip"
    stem, ext = os.path.splitext(base)
    return "%s-%s%s" % (stem, stamp or time.strftime("%Y%m%d", time.gmtime()), ext or ".zip")


def _fetch_once(url, dest_part, user_agent, timeout, opener, validate):
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with opener(req, timeout=timeout) as resp:
        expected = resp.headers.get("Content-Length") if getattr(resp, "headers", None) else None
        written = 0
        with open(dest_part, "wb") as out:
            while True:
                block = resp.read(_CHUNK)
                if not block:
                    break
                out.write(block)
                written += len(block)
            out.flush()
            os.fsync(out.fileno())
    if expected is not None and int(expected) != written:
        raise DownloadError("short read: %d of %s bytes" % (written, expected))
    if not validate(dest_part):
        raise DownloadError("downloaded file failed validation (%s)"
                            % getattr(validate, "__name__", "check"))
    return written


def download(url: str, dest_dir: str, user_agent: str, timeout: float = 60,
             retries: int = 4, backoff: float = 5,
             opener: Callable = urllib.request.urlopen,
             sleep: Callable[[float], None] = time.sleep,
             stamp: Optional[str] = None,
             validate: Callable[[str], bool] = zipfile.is_zipfile) -> str:
    """Fetch url into dest_dir/<stem>-YYYYMMDD.<ext> and return that path.

    Retries `retries` times after the first attempt, sleeping backoff * 2**attempt.
    4xx responses other than 408/429 are not retried.
    """
    os.makedirs(dest_dir, exist_ok=True)
    final = os.path.join(dest_dir, dated_name(url, stamp))
    part = final + ".part"
    last_exc = None
    for attempt in range(retries + 1):
        try:
            t0 = time.time()
            size = _fetch_once(url, part, user_agent, timeout, opener, validate)
            os.replace(part, final)
            log.info("downloaded %s -> %s (%.1f MB in %.1fs)",
                     url, final, size / 1e6, time.time() - t0)
            return final
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if 400 <= exc.code < 500 and exc.code not in (408, 429):
                _cleanup(part)
                raise DownloadError("%s: HTTP %d" % (url, exc.code)) from exc
        except (urllib.error.URLError, OSError, DownloadError) as exc:
            last_exc = exc
        _cleanup(part)
        if attempt < retries:
            wait = backoff * (2 ** attempt)
            log.warning("download attempt %d/%d failed (%s); retrying in %.0fs",
                        attempt + 1, retries + 1, last_exc, wait)
            sleep(wait)
    raise DownloadError("%s: failed after %d attempts: %s" % (url, retries + 1, last_exc))


def _cleanup(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def prune(dest_dir: str, url: str, keep: int) -> List[str]:
    """Keep the newest `keep` dated copies of this URL's file; return the paths removed."""
    stem, ext = os.path.splitext(os.path.basename(url.split("?", 1)[0]))
    ext = ext or ".zip"
    prefix = stem + "-"
    copies = sorted(
        n for n in os.listdir(dest_dir)
        if n.startswith(prefix) and n.endswith(ext) and n[len(prefix):-len(ext)].isdigit())
    removed = []
    for name in copies[:-keep] if keep > 0 else copies:
        path = os.path.join(dest_dir, name)
        os.remove(path)
        removed.append(path)
    return removed
