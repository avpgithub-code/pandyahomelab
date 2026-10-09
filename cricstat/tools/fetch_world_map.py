"""Build the cricket world map (assets/world-map.json) from Natural Earth (public domain).

Source: Natural Earth 1:10m admin-0 countries, **India's point of view** (ne_10m_admin_0_countries_ind:
borders as India officially shows them, incl. Jammu & Kashmir and Ladakh), plus the 1:10m map units for
England, Wales, Scotland and Northern Ireland (cricket splits the UK; Ireland is one all-island team).
Natural Earth is public domain (naturalearthdata.com/about/terms-of-use): no credit required, given anyway.

Each shape gets its ISO-ish code (ADM0_A3 / GU_A3), name, an SVG path in the Equal Earth projection
(simplified, rounded to 0.1 px of a 1000 px-wide map), its label point and area, so tiny members
(Bermuda, Jersey, Hong Kong...) can be drawn as dots. Antarctica is dropped. Which cricket team a shape
belongs to is decided in the page (assets/worldmap.js), not here.

    python3 cricstat/tools/fetch_world_map.py [--cache DIR]
"""
import argparse
import json
import math
import os
import struct
import urllib.request

BASE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/10m_cultural/"
COUNTRIES = "ne_10m_admin_0_countries_ind"
UNITS = "ne_10m_admin_0_map_units"
UK_UNITS = {"ENG", "WLS", "SCT", "NIR"}
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "staging", "web", "assets", "world-map.json")
WIDTH = 1000.0
TOLERANCE = 0.35          # px: Douglas-Peucker tolerance
MIN_RING = 0.6            # px²: smaller islands are dropped (the shape's dot keeps it clickable)
UA = "cricstat-map-builder/1.0 (pandyahomelab.com/cricket; privacy@pandyahomelab.com)"


def fetch(cache, name):
    os.makedirs(cache, exist_ok=True)
    for ext in ("shp", "dbf"):
        path = os.path.join(cache, name + "." + ext)
        if not os.path.exists(path):
            req = urllib.request.Request(BASE + name + "." + ext, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r, open(path, "wb") as f:
                f.write(r.read())
    return os.path.join(cache, name)


def read_dbf(path):
    with open(path, "rb") as f:
        data = f.read()
    n, hlen, rlen = struct.unpack("<IHH", data[4:12])
    fields, pos = [], 32
    while data[pos] != 0x0D:
        name = data[pos:pos + 11].split(b"\0")[0].decode("ascii")
        fields.append((name, data[pos + 16]))
        pos += 32
    rows = []
    for i in range(n):
        rec, off, row = data[hlen + i * rlen: hlen + (i + 1) * rlen], 1, {}
        for name, size in fields:
            row[name] = rec[off:off + size].decode("utf-8", "replace").strip()
            off += size
        rows.append(row)
    return rows


def read_shp(path):
    """Polygon records (type 5) → list of rings (lon, lat) per record."""
    with open(path, "rb") as f:
        data = f.read()
    pos, shapes = 100, []
    while pos < len(data):
        _, length = struct.unpack(">ii", data[pos:pos + 8])
        rec = data[pos + 8: pos + 8 + length * 2]
        pos += 8 + length * 2
        if struct.unpack("<i", rec[:4])[0] != 5:
            shapes.append([])
            continue
        nparts, npts = struct.unpack("<ii", rec[36:44])
        parts = list(struct.unpack("<%di" % nparts, rec[44:44 + 4 * nparts])) + [npts]
        pts = struct.unpack("<%dd" % (2 * npts), rec[44 + 4 * nparts: 44 + 4 * nparts + 16 * npts])
        shapes.append([[(pts[2 * j], pts[2 * j + 1]) for j in range(parts[k], parts[k + 1])]
                       for k in range(nparts)])
    return shapes


# Equal Earth projection (Šavrič, Patterson, Jenny 2018)
A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796
M = math.sqrt(3) / 2


def project(lon, lat):
    t = math.asin(M * math.sin(math.radians(lat)))
    t2 = t * t
    t6 = t2 * t2 * t2
    x = math.radians(lon) * math.cos(t) / (M * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2)))
    y = t * (A1 + A2 * t2 + t6 * (A3 + A4 * t2))
    return x, y


XMAX = project(180, 0)[0]
YMAX = project(0, 90)[1]
SCALE = WIDTH / (2 * XMAX)


def to_px(lon, lat):
    x, y = project(lon, lat)
    return (x + XMAX) * SCALE, (YMAX - y) * SCALE


def simplify(pts, tol):
    if len(pts) < 4:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        (x1, y1), (x2, y2) = pts[a], pts[b]
        dx, dy = x2 - x1, y2 - y1
        norm = math.hypot(dx, dy) or 1e-9
        best, idx = 0.0, -1
        for i in range(a + 1, b):
            d = abs(dy * (pts[i][0] - x1) - dx * (pts[i][1] - y1)) / norm
            if d > best:
                best, idx = d, i
        if best > tol and idx > 0:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(pts, keep) if k]


def area(pts):
    return abs(sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1] for i in range(len(pts)))) / 2


def shape(code, name, rings):
    paths, total, biggest = [], 0.0, (0.0, None)
    for ring in rings:
        px = [to_px(lon, max(-89.9, min(89.9, lat))) for lon, lat in ring]
        a = area(px)
        if a > biggest[0]:
            biggest = (a, px)
        if a < MIN_RING:
            continue
        mid = len(px) // 2            # a closed ring starts and ends on one point: simplify each half
        s = simplify(px[:mid + 1], TOLERANCE)[:-1] + simplify(px[mid:], TOLERANCE)
        if len(s) < 4:
            continue
        total += a
        paths.append("M" + "L".join("%.1f,%.1f" % p for p in s[:-1]) + "Z")
    ring = biggest[1] or []
    cx = sum(p[0] for p in ring) / max(len(ring), 1)
    cy = sum(p[1] for p in ring) / max(len(ring), 1)
    return {"code": code, "name": name, "d": "".join(paths), "x": round(cx, 1), "y": round(cy, 1),
            "area": round(total, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=os.path.join(HERE, "staging", "natural-earth"))
    args = ap.parse_args()
    out = []
    base = fetch(args.cache, COUNTRIES)
    for row, rings in zip(read_dbf(base + ".dbf"), read_shp(base + ".shp")):
        code = row["ADM0_A3"]
        if code in ("ATA", "GBR") or not rings:
            continue
        out.append(shape(code, row["NAME"], rings))
    base = fetch(args.cache, UNITS)
    for row, rings in zip(read_dbf(base + ".dbf"), read_shp(base + ".shp")):
        if row["GU_A3"] in UK_UNITS and rings:
            out.append(shape(row["GU_A3"], row["NAME"], rings))
    doc = {"source": "Natural Earth 1:10m admin-0 countries (India's point of view) and map units",
           "licence": "Public domain (naturalearthdata.com/about/terms-of-use)",
           "projection": "Equal Earth", "width": WIDTH, "height": round(2 * YMAX * SCALE, 1),
           "shapes": sorted(out, key=lambda s: s["code"])}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, separators=(",", ":"))
    print(json.dumps({"shapes": len(out), "bytes": os.path.getsize(OUT), "out": OUT}))


if __name__ == "__main__":
    main()
