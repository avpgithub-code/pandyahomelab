"""Tail a log file by byte offset, with inode tracking to handle rotation."""
import os
from typing import List, Optional


class LogTailer:
    """Resilient log tailer.

    On each `read_new()` call:
      1. Check the file's inode — if it changed (rotation / replacement), reset offset to 0
      2. Seek to the last known offset
      3. Read everything new, return as list of stripped lines
      4. Advance the offset
    """

    def __init__(self, path: str, start_offset: int = 0, start_inode: Optional[int] = None):
        self.path = path
        self.position = start_offset
        self.inode = start_inode or self._current_inode()

        # Guard: if checkpoint offset is beyond current file size, the file was rotated
        # or truncated. Reset to start.
        try:
            current_size = os.path.getsize(path)
            if current_size < self.position:
                self.position = 0
        except FileNotFoundError:
            pass

    def _current_inode(self) -> Optional[int]:
        try:
            return os.stat(self.path).st_ino
        except FileNotFoundError:
            return None

    def read_new(self) -> List[str]:
        new_inode = self._current_inode()
        if new_inode is None:
            # File doesn't exist yet (Nginx hasn't written anything)
            return []

        # Detect rotation: inode changed, so reset
        if self.inode is not None and new_inode != self.inode:
            self.position = 0
        self.inode = new_inode

        try:
            with open(self.path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self.position)
                lines = f.readlines()
                self.position = f.tell()
        except FileNotFoundError:
            return []

        return [ln.rstrip("\n") for ln in lines if ln.strip()]
