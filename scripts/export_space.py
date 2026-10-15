"""Export Space-mode results (results/space/<name>/) for the web app → web/public/data/space_<name>.json + space_index.json (+ map image).

The backend serves it at /data/space like every other exported JSON. Flood/permanent-water pixels are vectorised
(simplified 10 m) and reprojected to WGS84; only hit buildings are exported (all roads/bridges keep their hit flag).
Run: python scripts/export_space.py --name dharali
"""
import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.warp import transform_geom
from shapely.geometry import mapping, shape

from flowdir import flowdir
from s2_thumbs import thumbs

ROOT = Path(__file__).resolve().parents[1]


def polygons(tif: Path, classes: dict) -> dict:
    with rasterio.open(tif) as src:
        a, T, crs = src.read(1), src.transform, src.crs
    feats = []
    for cls, name in classes.items():
        m = (a == cls).astype("uint8")
        for g, v in shapes(m, mask=m.astype(bool), transform=T):
            geom = shape(g).simplify(10, preserve_topology=True)
            if geom.is_empty or geom.area < 400:  # drop specks < 400 m²
                continue
            feats.append({"type": "Feature", "geometry": transform_geom(crs, "EPSG:4326", mapping(geom), precision=5),
                          "properties": {"class": name, "area_m2": round(geom.area)}})
    return {"type": "FeatureCollection", "features": feats}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--name", default="dharali"); n = ap.parse_args().name
    d = ROOT / "results/space" / n
    s = json.loads((d / "summary.json").read_text(encoding="utf-8"))
    meta_p = ROOT / "models/space/floodseg_meta.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
    load = lambda f: json.loads((d / f).read_text(encoding="utf-8"))  # noqa: E731
    b = load("buildings_hit.geojson"); b["features"] = [f for f in b["features"] if f["properties"]["hit"]]
    out = {"name": n, "event_utc": s["event_utc"], "bbox": s["bbox"], "detector": s.get("detector"), "osm_snapshot": s["osm_snapshot"],
           "s1_pairs": s["s1_pairs"], "flood": s["flood"], "damage": s["damage"], "cutoff": load("cutoff.json"),
           "model": {k: meta.get(k) for k in ("arch", "flood_threshold", "water_threshold", "test_scores_unseen_events", "training_data", "trained_utc")},
           "layers": {"flood": polygons(d / "flood_class.tif", {1: "flood", 3: "permanent water"}), "buildings_hit": b,
                      "roads": load("roads_hit.geojson"), "bridges": load("bridges_hit.geojson")},
           "debris": ({"summary": s["debris_rule"], "cutoff": load("cutoff_debris.json"),
                       "polygons": polygons(d / "debris_class.tif", {2: "possible debris"}),
                       "buildings_hit": {"type": "FeatureCollection", "features": [f for f in load("buildings_debris.geojson")["features"] if f["properties"]["hit"]]},
                       "roads": {"type": "FeatureCollection", "features": [f for f in load("roads_debris.geojson")["features"] if f["properties"]["hit"]]}}
                      if (d / "debris_class.tif").exists() else None),
           "sitrep": (d / "sitrep.md").read_text(encoding="utf-8") if (d / "sitrep.md").exists() else "",
           "s2": s.get("s2"), "runtime_s": s.get("runtime_s"),
           "rescue": load("rescue.json") if (d / "rescue.json").exists() else None,
           "emsr_check": load("emsr_check.json") if (d / "emsr_check.json").exists() else None,
           "s2_images": thumbs(n, s.get("s2"), s["bbox"]),
           "flowdir": flowdir(d / "dem.tif") if (d / "dem.tif").exists() else None,
           "debris_conf": polygons(d / "debris_conf.tif", {3: "radar + optical"}) if (d / "debris_conf.tif").exists() else None}
    web = ROOT / "web/public/data"
    (web / f"space_{n}.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    idx_p = web / "space_index.json"
    idx = [e for e in (json.loads(idx_p.read_text(encoding="utf-8")) if idx_p.exists() else []) if e["name"] != n]
    idx.append({"name": n, "event_utc": s["event_utc"], "bbox": s["bbox"], "checked": out["emsr_check"] is not None})
    idx_p.write_text(json.dumps(sorted(idx, key=lambda e: e["event_utc"], reverse=True)), encoding="utf-8")
    img = ROOT / "web/public/img/space"; img.mkdir(parents=True, exist_ok=True)
    if (d / "map.png").exists():
        shutil.copy(d / "map.png", img / f"{n}.png")
    if (d / "emsr_check.png").exists():
        shutil.copy(d / "emsr_check.png", img / f"{n}_emsr.png")
    print(f"space.json: {len(out['layers']['flood']['features'])} flood polygons, {len(b['features'])} hit buildings, "
          f"space_{n}.json {(web / f'space_{n}.json').stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
