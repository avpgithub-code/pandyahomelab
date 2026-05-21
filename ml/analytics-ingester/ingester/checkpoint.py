"""Persist the tailer's byte offset + inode atomically across restarts."""
import json
import os
from typing import Optional, Tuple


class Checkpoint:
    """Atomic file-based checkpoint. Writes via temp-file + rename for crash safety."""

    def __init__(self, path: str):
        self.path = path
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)

    def read(self) -> Tuple[int, Optional[int]]:
        """Returns (offset, inode). Both 0/None if no checkpoint exists yet."""
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
            return int(data.get("offset", 0)), data.get("inode")
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            return 0, None

    def write(self, offset: int, inode: Optional[int]) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"offset": offset, "inode": inode}, f)
        os.replace(tmp, self.path)  # atomic on POSIX
