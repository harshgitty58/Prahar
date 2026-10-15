"""Sentinel-2 evidence 'when the sky is clear' (Track B). Per-pixel, only where the L2A scene classification
(SCL) says clear, in both the pre- and post-event image:
- water: MNDWI = (green - SWIR1) / (green + SWIR1) > 0  (Xu 2006, Int. J. Remote Sensing 27(14)); new water = water
  after, not water before.
- debris / scour: vegetated before (NDVI >= 0.2) and barren after (NDVI <= 0.1), not water. USGS NDVI guide:
  '0.1 and below = barren rock, sand or snow; 0.2-0.3 = shrub and grassland'.
Scenes are chosen by the clear share INSIDE the area (tile cloud cover says little about one valley).
"""
import numpy as np
import pandas as pd

from . import data, flood

SCL_CLEAR = (4, 5, 6, 7)        # vegetation, not-vegetated, water, unclassified (ESA L2A SCL)
MNDWI_WATER = 0.0               # Xu (2006)
NDVI_VEG, NDVI_BARE = 0.2, 0.1  # USGS NDVI ranges
MIN_CLEAR = 0.05                # skip a scene with < 5 % clear pixels in the area


def _refl(item, grid, band):
    rb = (item["assets"][band].get("raster:bands") or [{}])[0]
    x = data._warp(item["assets"][band]["href"], grid)
    return x * rb.get("scale", 1e-4) + rb.get("offset", 0.0)


def _best(bbox, grid, start, end, n=4):
    best = (0.0, None, None)
    for it in data.s2_clear(bbox, start, end, max_cloud=95)[:n]:
        scl = data._warp(it["assets"]["scl"]["href"], grid, data.Resampling.nearest)
        clear = np.isin(scl, SCL_CLEAR)
        if clear.mean() > best[0]:
            best = (float(clear.mean()), it, clear)
    return best


def evidence(bbox, grid, event: pd.Timestamp, pre_days=30, post_days=12) -> dict | None:
    """Return per-pixel S2 masks + metadata, or None when no usable clear scene exists."""
    fp, pre, cpre = _best(bbox, grid, event - pd.Timedelta(days=pre_days), event - pd.Timedelta(hours=1))
    fq, post, cpost = _best(bbox, grid, event, event + pd.Timedelta(days=post_days))
    meta = {"pre": pre and pre["id"], "post": post and post["id"], "pre_clear": round(fp, 3), "post_clear": round(fq, 3)}
    if pre is None or post is None or fp < MIN_CLEAR or fq < MIN_CLEAR:
        return {"meta": meta | {"used": False, "reason": "no clear Sentinel-2 view of the area (monsoon cloud): radar only"}}
    ok = cpre & cpost
    ind = {}
    for k, it in (("pre", pre), ("post", post)):
        g, r, n, s = (_refl(it, grid, b) for b in ("green", "red", "nir", "swir16"))
        with np.errstate(invalid="ignore", divide="ignore"):
            ind[k] = {"mndwi": (g - s) / (g + s), "ndvi": (n - r) / (n + r)}
    w_pre, w_post = ind["pre"]["mndwi"] > MNDWI_WATER, ind["post"]["mndwi"] > MNDWI_WATER
    # same minimum-cluster rule as the radar map (UN-SPIDER: a pixel with <= 8 connected neighbours is removed);
    # without it shaded forest and cloud-shadow edges leave isolated specks on the slopes
    new_water = flood.drop_small(ok & w_post & ~w_pre)
    debris = flood.drop_small(ok & (ind["pre"]["ndvi"] >= NDVI_VEG) & (ind["post"]["ndvi"] <= NDVI_BARE) & ~w_post)
    meta |= {"used": True, "both_clear": round(float(ok.mean()), 3)}
    return {"meta": meta, "clear": ok, "new_water": new_water, "debris": debris}
