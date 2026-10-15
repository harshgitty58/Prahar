"""Space mode — raw inputs for any area (bbox, WGS84) and flood date, on one common UTM grid.

Sources (all keyless):
  Sentinel-1 RTC (gamma0, linear) — Microsoft Planetary Computer STAC, collection sentinel-1-rtc (SAS token endpoint)
  Sentinel-2 L2A                  — Element 84 Earth Search STAC (AWS Open Data)
  Copernicus DEM GLO-30           — AWS Open Data bucket copernicus-dem-30m (COG per 1°×1° tile)
  OpenStreetMap before the event  — ohsome API (snapshot timestamp before the event; latest available is used if later)
"""
import math
from pathlib import Path
import hashlib
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
import rasterio
import requests
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject, transform_bounds

PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
PC_SAS = "https://planetarycomputer.microsoft.com/api/sas/v1/token/{collection}"
ES_STAC = "https://earth-search.aws.element84.com/v1/search"
DEM_URL = "https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM/Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM.tif"
OHSOME_HIST = "https://api.ohsome.org/v1/elementsFullHistory/geometry"
UA = {"User-Agent": "PRAHAR-course-project/0.2"}


@dataclass
class Grid:
    crs: str
    transform: rasterio.Affine
    width: int
    height: int
    bbox: tuple  # WGS84 (W, S, E, N)

    @property
    def res(self) -> float:
        return self.transform.a


def make_grid(bbox, res=10.0) -> Grid:
    w, s, e, n = bbox
    zone = int((w + e) / 2 // 6) + 31
    crs = f"EPSG:{32600 + zone if (s + n) / 2 >= 0 else 32700 + zone}"
    x0, y0, x1, y1 = transform_bounds("EPSG:4326", crs, w, s, e, n)
    width, height = int(math.ceil((x1 - x0) / res)), int(math.ceil((y1 - y0) / res))
    return Grid(crs, from_origin(x0, y1, res, res), width, height, tuple(bbox))


def _warp(href: str, grid: Grid, resampling=Resampling.bilinear, band=1) -> np.ndarray:
    out = np.full((grid.height, grid.width), np.nan, dtype="float32")
    with rasterio.open(href) as src:
        reproject(rasterio.band(src, band), out, dst_transform=grid.transform, dst_crs=grid.crs, resampling=resampling,
                  src_nodata=src.nodata, dst_nodata=np.nan)
    return out


# ------------------------------------------------------------------ Sentinel-1
def s1_pairs(bbox, event: pd.Timestamp, max_gap_days=12, window_days=24) -> list[dict]:
    """Before/after pairs from the SAME relative orbit (Track B tip: same track, same time of day).
    before = last acquisition before the event, after = first acquisition at/after it (≤ max_gap_days later)."""
    t0, t1 = event - pd.Timedelta(days=window_days), event + pd.Timedelta(days=window_days)
    q = {"collections": ["sentinel-1-rtc"], "bbox": list(bbox), "datetime": f"{t0:%Y-%m-%dT%H:%M:%SZ}/{t1:%Y-%m-%dT%H:%M:%SZ}", "limit": 200}
    feats = requests.post(PC_STAC, json=q, timeout=120).json().get("features", [])
    pairs = []
    for orbit, g in pd.DataFrame([{"id": f["id"], "t": pd.Timestamp(f["properties"]["datetime"]).tz_localize(None),
                                    "orbit": f["properties"].get("sat:relative_orbit"), "state": f["properties"].get("sat:orbit_state"), "f": f}
                                   for f in feats]).groupby("orbit") if feats else []:
        before, after = g[g.t < event].sort_values("t"), g[g.t >= event].sort_values("t")
        if len(before) and len(after) and (after.t.iloc[0] - event).days <= max_gap_days:
            b, a = before.iloc[-1], after.iloc[0]
            b2 = before.iloc[-2] if len(before) > 1 else b        # second pre-event image (AI model input)
            pairs.append({"orbit": int(orbit), "state": a.state, "before": b.f, "after": a.f, "before2": b2.f,
                          "before_t": str(b.t), "after_t": str(a.t), "before2_t": str(b2.t)})
    return sorted(pairs, key=lambda p: pd.Timestamp(p["after_t"]))


_SAS: dict = {}
CACHE = Path(__file__).resolve().parents[2] / "results/space/_cache"


def _sas(collection: str) -> str:
    """Keyless Planetary Computer SAS token, reused while valid (fetching one per image gets rate-limited)."""
    tok, t = _SAS.get(collection, (None, 0.0))
    if tok and time.time() - t < 40 * 60:
        return tok
    for wait in (0, 5, 15, 30, 60):
        time.sleep(wait)
        r = requests.get(PC_SAS.format(collection=collection), timeout=60)
        if r.ok and "token" in r.json():
            _SAS[collection] = (r.json()["token"], time.time())
            return _SAS[collection][0]
    raise RuntimeError(f"Planetary Computer SAS token unavailable ({r.status_code})")


def s1_db(item: dict, grid: Grid, pol="vh") -> np.ndarray:
    """Sentinel-1 RTC backscatter in dB on the grid; cached on disk per image/polarisation/grid (fast re-runs)."""
    key = CACHE / f"{item['id']}_{pol}_{hashlib.md5(repr((grid.crs, tuple(grid.transform), grid.width, grid.height)).encode()).hexdigest()[:10]}.npy"
    if key.exists():
        return np.load(key)
    lin = _warp(f"{item['assets'][pol]['href']}?{_sas('sentinel-1-rtc')}", grid)
    with np.errstate(divide="ignore", invalid="ignore"):
        db = np.where(lin > 0, 10 * np.log10(lin), np.nan).astype("float32")
    CACHE.mkdir(parents=True, exist_ok=True)
    np.save(key, db)
    return db


# ------------------------------------------------------------------ Sentinel-2
def s2_clear(bbox, start: pd.Timestamp, end: pd.Timestamp, max_cloud=20) -> list[dict]:
    q = {"collections": ["sentinel-2-l2a"], "bbox": list(bbox), "datetime": f"{start:%Y-%m-%dT00:00:00Z}/{end:%Y-%m-%dT23:59:59Z}",
         "query": {"eo:cloud_cover": {"lt": max_cloud}}, "limit": 100}
    return sorted(requests.post(ES_STAC, json=q, timeout=120).json().get("features", []), key=lambda f: f["properties"]["eo:cloud_cover"])


def s2_bands(item: dict, grid: Grid, bands=("green", "red", "nir", "swir16", "scl")) -> dict:
    return {b: _warp(item["assets"][b]["href"], grid, Resampling.nearest if b == "scl" else Resampling.bilinear) for b in bands}


# ------------------------------------------------------------------ Copernicus DEM
def dem(grid: Grid) -> np.ndarray:
    w, s, e, n = grid.bbox
    out = np.full((grid.height, grid.width), np.nan, dtype="float32")
    for lat in range(math.floor(s), math.floor(n) + 1):
        for lon in range(math.floor(w), math.floor(e) + 1):
            href = DEM_URL.format(ns="N" if lat >= 0 else "S", lat=abs(lat), ew="E" if lon >= 0 else "W", lon=abs(lon))
            part = _warp(href, grid)
            out = np.where(np.isnan(out), part, out)
    return out


def slope_percent(z: np.ndarray, res: float) -> np.ndarray:
    gy, gx = np.gradient(z, res)
    return 100 * np.hypot(gx, gy)


# ------------------------------------------------------------------ OpenStreetMap before the event
OSM_FILTERS = {
    "buildings": "building=* and geometry:polygon",
    "roads": "highway in (motorway, trunk, primary, secondary, tertiary, unclassified, residential, track, service, path) and geometry:line",
    "bridges": "bridge=* and bridge!=no and highway=* and geometry:line",
    "places": "place in (city, town, village, hamlet, suburb, neighbourhood) and geometry:point",
    "hospitals": "amenity in (hospital, clinic) or healthcare in (hospital, clinic)",
    "water": "(natural=water or waterway=riverbank or water=river) and geometry:polygon",
    "waterways": "waterway in (river, stream, canal, drain) and geometry:line",
}
OHSOME_LATEST = pd.Timestamp("2026-07-27")


def osm_before(bbox, event: pd.Timestamp, layers=tuple(OSM_FILTERS)) -> dict:
    """GeoJSON per layer as mapped the day before the event (or the latest ohsome snapshot if the event is newer)."""
    ts = min(event.normalize() - pd.Timedelta(days=1), OHSOME_LATEST)
    # /elements/geometry is blocked for anonymous use; /elementsFullHistory/geometry over [ts-1d, ts] keeping the
    # versions still valid at ts reproduces the snapshot exactly
    out, end = {}, f"{ts:%Y-%m-%d}T00:00:00Z"
    for name in layers:
        r = requests.post(OHSOME_HIST, data={"bboxes": ",".join(map(str, bbox)), "time": f"{ts - pd.Timedelta(days=1):%Y-%m-%d},{ts:%Y-%m-%d}",
                                             "filter": OSM_FILTERS[name], "properties": "tags"}, headers=UA, timeout=300)
        r.raise_for_status()
        fc = r.json()
        fc["features"] = [f for f in fc.get("features", []) if f.get("properties", {}).get("@validTo") == end]
        out[name] = fc
    out["_snapshot"] = f"{ts:%Y-%m-%d}"
    return out
