"""Download text8 and GloVe 6B 100d into data/raw/, checksum-verified.

Idempotent: a file whose sha256 already matches is skipped, and a download that
doesn't match its pinned checksum is deleted rather than left half-trusted.

    python scripts/fetch_data.py [--data-dir data]
"""
import argparse
import hashlib
import os
import sys
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_logic.loaders.sources import GLOVE_FILES, TEXT8, glove_url, raw_dir  # noqa: E402


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, dest: str, expected: str) -> None:
    name = os.path.basename(dest)
    if os.path.exists(dest) and sha256(dest) == expected:
        print(f"{name}: already present")
        return
    print(f"{name}: downloading {url}")
    tmp = dest + ".part"
    urllib.request.urlretrieve(url, tmp)
    actual = sha256(tmp)
    if actual != expected:
        os.remove(tmp)
        sys.exit(f"{name}: sha256 mismatch (got {actual}, expected {expected})")
    os.replace(tmp, dest)
    print(f"{name}: ok ({os.path.getsize(dest) / 1e6:.1f} MB)")


def main(data_dir: str) -> None:
    raw = raw_dir(data_dir)
    os.makedirs(raw, exist_ok=True)
    zip_path = os.path.join(raw, TEXT8["file"])
    fetch(TEXT8["url"], zip_path, TEXT8["sha256"])
    if not os.path.exists(os.path.join(raw, "text8")):
        zipfile.ZipFile(zip_path).extractall(raw)
        print("text8: extracted")
    for name, expected in GLOVE_FILES.items():
        fetch(glove_url(name), os.path.join(raw, name), expected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", default="data")
    main(parser.parse_args().data_dir)
