"""Sentinel-2 true-colour (TCI 'visual') before/after images for the dashboard's before/after slider.
Uses the same pre/post scenes the pipeline chose (summary.json -> s2). Written on a lon/lat grid that matches the
event bbox exactly, so the map can place them as image sources. Output: web/public/img/space/<name>_s2_{pre,post}.jpg
"""
from pathlib import Path

import numpy as np
import rasterio
import requests
from PIL import Image
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject

ROOT = Path(__file__).resolve().parents[1]
ITEM = "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/{}"


def thumbs(name: str, s2: dict | None, bbox, max_px=1400) -> dict | None:
    if not s2 or not s2.get("pre") or not s2.get("post"):
        return None
    w, s, e, n = bbox
    W = max_px if (e - w) >= (n - s) else int(max_px * (e - w) / (n - s))
    H = int(W * (n - s) / (e - w))
    T = from_bounds(w, s, e, n, W, H)
    out = {}
    for k in ("pre", "post"):
        href = requests.get(ITEM.format(s2[k]), timeout=60).json()["assets"]["visual"]["href"]
        rgb = np.zeros((3, H, W), "uint8")
        with rasterio.open(href) as src:
            for b in range(3):
                reproject(rasterio.band(src, b + 1), rgb[b], dst_transform=T, dst_crs="EPSG:4326", resampling=Resampling.bilinear)
        f = ROOT / "web/public/img/space" / f"{name}_s2_{k}.jpg"
        f.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(np.moveaxis(rgb, 0, -1)).save(f, quality=82)
        out[k] = {"url": f"/img/space/{f.name}", "date": s2[k].split("_")[2]}
    out["bounds"] = [w, s, e, n]
    return out
