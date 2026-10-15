"""D8 flow directions for the flood-path tracer (Track B bonus), from the Copernicus DEM of a Space-mode run.

Priority-Flood (Barnes, Lehman & Mulla 2014, Computers & Geosciences 62) seeded from the area's edge: every cell drains
to the neighbour it was reached from, so pits are routed through instead of trapping the path. The grid is lon/lat
(~30 m, the DEM's native spacing) so the browser can map a click straight to a cell. Direction codes 0-7 = E, SE, S,
SW, W, NW, N, NE (row down = south); 255 = edge/outlet.
"""
import base64
import heapq
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject, transform_bounds

STEP = 0.0003  # degrees (~30 m)
DR = [0, 1, 1, 1, 0, -1, -1, -1]
DC = [1, 1, 0, -1, -1, -1, 0, 1]


def flowdir(dem_tif: Path) -> dict:
    with rasterio.open(dem_tif) as src:
        w, s, e, n = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
        W, H = int((e - w) / STEP), int((n - s) / STEP)
        T = rasterio.transform.from_origin(w, n, STEP, STEP)
        z = np.full((H, W), np.nan, "float32")
        reproject(rasterio.band(src, 1), z, dst_transform=T, dst_crs="EPSG:4326", resampling=Resampling.bilinear, dst_nodata=np.nan)
    z = np.where(np.isfinite(z), z, np.nanmax(z) + 1)
    d = np.full((H, W), 255, "uint8")
    seen = np.zeros((H, W), bool)
    pq = []
    for r in range(H):
        for c in (0, W - 1):
            heapq.heappush(pq, (float(z[r, c]), r, c)); seen[r, c] = True
    for c in range(1, W - 1):
        for r in (0, H - 1):
            heapq.heappush(pq, (float(z[r, c]), r, c)); seen[r, c] = True
    while pq:
        h, r, c = heapq.heappop(pq)
        for k in range(8):
            rr, cc = r + DR[k], c + DC[k]
            if 0 <= rr < H and 0 <= cc < W and not seen[rr, cc]:
                seen[rr, cc] = True
                d[rr, cc] = (k + 4) % 8          # fallback: drain back towards (r, c)
                f = max(h + 1e-3, float(z[rr, cc]))  # epsilon fill: every cell keeps a strictly lower way out
                z[rr, cc] = f
                heapq.heappush(pq, (f, rr, cc))
    # D8 steepest descent on the filled surface (cell size in metres: lon step shrinks with latitude)
    lat = n - (np.arange(H) + 0.5) * STEP
    dx = STEP * 111320 * np.cos(np.radians(lat))[:, None]
    dy = STEP * 110540
    best = np.zeros((H, W), "float32")
    for k in range(8):
        nb = np.full((H, W), np.inf, "float32")
        r0, r1 = max(0, -DR[k]), H - max(0, DR[k])
        c0, c1 = max(0, -DC[k]), W - max(0, DC[k])
        nb[r0:r1, c0:c1] = z[r0 + DR[k]:r1 + DR[k], c0 + DC[k]:c1 + DC[k]]
        g = (z - nb) / np.hypot(dx * DC[k], dy * DR[k])
        better = g > best
        best = np.where(better, g, best)
        d = np.where(better, k, d).astype("uint8")
    d[0, :] = d[-1, :] = d[:, 0] = d[:, -1] = 255   # area edge = outlet
    return {"west": round(w, 6), "north": round(n, 6), "step": STEP, "w": W, "h": H,
            "dr": DR, "dc": DC, "dir_b64": base64.b64encode(d.tobytes()).decode()}
