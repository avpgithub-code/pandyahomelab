"""Recognise the owner's own visits by their home IP, so the dashboard can keep them
out of the real-visitor numbers and show them separately.

The home IP is found by resolving a DDNS hostname (HOME_IP_HOST, e.g. the Synology
DDNS name). DSM keeps that name pointed at the current public IP, so no third-party
"what's my IP" service is involved. Only the salted hash is stored — never the IP —
in analytics.home_ips. Every hash the home connection has ever had stays in the
table, so past visits stay excluded after the ISP changes the address.
"""
import asyncio
import logging
import os
import socket

from app.db import get_cursor
from app.ip_hasher import hash_ip

logger = logging.getLogger("admin-portal.home-ip")

REFRESH_SECONDS = 600

UPSERT_SQL = """
INSERT INTO analytics.home_ips (ip_hash) VALUES (%s)
ON CONFLICT (ip_hash) DO UPDATE SET last_seen = NOW()
"""


def refresh_home_ip() -> bool:
    """Resolve HOME_IP_HOST and record its hash. Returns False when off or failed."""
    host = os.environ.get("HOME_IP_HOST", "").strip()
    if not host:
        return False
    try:
        ip = socket.gethostbyname(host)
    except OSError as e:
        logger.warning(f"could not resolve HOME_IP_HOST {host}: {e}")
        return False
    with get_cursor() as cur:
        cur.execute(UPSERT_SQL, (hash_ip(ip),))
        cur.connection.commit()
    return True


async def refresh_loop() -> None:
    """Background task: re-resolve every 10 minutes so an IP change is picked up."""
    loop = asyncio.get_running_loop()
    while True:
        try:
            await loop.run_in_executor(None, refresh_home_ip)
        except Exception as e:
            logger.warning(f"home IP refresh failed: {e}")
        await asyncio.sleep(REFRESH_SECONDS)
