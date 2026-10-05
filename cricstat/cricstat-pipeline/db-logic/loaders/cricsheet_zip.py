"""Read match files straight out of a Cricsheet zip (nothing is extracted to disk)."""
import hashlib
import os
import posixpath
import zipfile
from typing import Iterator, NamedTuple

from shared.exceptions import SourceError


class ZipMember(NamedTuple):
    name: str        # path inside the zip
    match_id: str    # file stem, e.g. "1496584"
    raw: bytes


def file_sha256(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


class CricsheetZip:
    """Iterates the *.json members of a Cricsheet download; counts everything else as skipped."""

    def __init__(self, path: str):
        if not os.path.isfile(path):
            raise SourceError("zip not found: %s" % path)
        if not zipfile.is_zipfile(path):
            raise SourceError("not a zip file: %s" % path)
        self.path = path
        self.skipped = []  # non-JSON member names

    def __iter__(self) -> Iterator[ZipMember]:
        with zipfile.ZipFile(self.path) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                base = posixpath.basename(info.filename)
                stem, ext = posixpath.splitext(base)
                if ext.lower() != ".json":
                    self.skipped.append(info.filename)
                    continue
                yield ZipMember(info.filename, stem, zf.read(info))
