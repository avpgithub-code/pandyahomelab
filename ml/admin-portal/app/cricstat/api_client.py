"""Reads cricstat-api's internal admin endpoints over cricstat-network (no file mounts)."""
import json
import os
import urllib.request

API_URL = os.environ.get("CRICSTAT_API_URL", "http://172.25.0.10:8000")


class CricstatUnavailable(Exception):
    pass


def get(path: str, timeout: float = 15) -> dict:
    try:
        with urllib.request.urlopen(API_URL + path, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))["data"]
    except Exception as exc:
        raise CricstatUnavailable("%s: %s" % (path, exc)) from exc
