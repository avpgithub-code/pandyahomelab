"""Download the GLUE QQP train + validation parquet files into data/qqp/.

Idempotent: a file whose sha256 already matches is skipped, and a download that
doesn't match the pinned checksum is deleted rather than left half-trusted.

    python scripts/fetch_qqp.py [--data-dir data/qqp]
"""
import argparse
import hashlib
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_logic.loaders.quora import QQP_FILES, qqp_local_path, qqp_url  # noqa: E402


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(data_dir: str) -> None:
    os.makedirs(data_dir, exist_ok=True)
    for split, (_, expected) in QQP_FILES.items():
        dest = qqp_local_path(data_dir, split)
        if os.path.exists(dest) and sha256(dest) == expected:
            print(f"{split}: already present ({dest})")
            continue
        print(f"{split}: downloading {qqp_url(split)}")
        tmp = dest + ".part"
        urllib.request.urlretrieve(qqp_url(split), tmp)
        actual = sha256(tmp)
        if actual != expected:
            os.remove(tmp)
            sys.exit(f"{split}: sha256 mismatch (got {actual}, expected {expected})")
        os.replace(tmp, dest)
        print(f"{split}: ok ({os.path.getsize(dest) / 1e6:.1f} MB)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", default="data/qqp")
    fetch(parser.parse_args().data_dir)
