"""Space mode end-to-end runner: area + flood date → flood/debris map (+ later: damage, cut-off, sitrep).

Run: python -m src.space.run --name dharali --bbox 78.70,30.98,78.90,31.10 --date "2025-08-05 08:15"
     (date in UTC; bbox W,S,E,N in WGS84). Outputs: results/space/<name>/
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.warp import transform_geom

from src.config import PROJECT_ROOT
from src.space import ai, data, flood, impact, optical, rescue


def save_tif(path: Path, arr: np.ndarray, grid: data.Grid):
    with rasterio.open(path, "w", driver="GTiff", height=grid.height, width=grid.width, count=1, dtype=arr.dtype,
                       crs=grid.crs, transform=grid.transform, compress="deflate") as dst:
        dst.write(arr, 1)


def rescue_step(out, grid, osm, z, cls, perm, deb, cut, cut_d) -> dict:
    """Who first (buildings per cut-off settlement) and where a helicopter could land (ICAO Annex 14 Vol II)."""
    cut_any = {}
    for layer, cc in (("water", cut), ("debris", cut_d)):
        for r in cc.get("settlements", []):
            if r["status"] == "CUT OFF" and r.get("name"):
                cut_any.setdefault(r["name"], r | {"by": []})["by"].append(layer)
    named = [r for r in cut.get("settlements", []) if r.get("name")]
    bld = rescue.people_at(osm, named, grid)
    chan = np.zeros(cls.shape, bool)       # the mapped river channel itself (pre-event OSM waterways)
    ww = [transform_geom("EPSG:4326", grid.crs, f["geometry"]) for f in osm["waterways"].get("features", []) if f.get("geometry")]
    if ww:
        chan = rasterize([(g, 1) for g in ww], out_shape=cls.shape, transform=grid.transform, all_touched=True, dtype="uint8").astype(bool)
    blocked = (cls != flood.NONE) | perm | chan
    if deb is not None:
        blocked |= deb == flood.DEBRIS
    lz = {x["settlement"]: x["sites"] for x in rescue.landing_zones(z, grid, blocked, osm, list(cut_any.values()))}
    ranked = sorted(({"name": k, "place": v.get("place"), "lon": v["lon"], "lat": v["lat"], "by": v["by"], "buildings": bld.get(k, 0),
                      "landing_sites": lz.get(k, [])} for k, v in cut_any.items()), key=lambda r: (-len(r["by"]), -r["buildings"]))
    (out / "rescue.json").write_text(json.dumps({"rule": "ICAO Annex 14 Vol II: FATO mean slope <= 3 %, local <= 5 %, side >= 1.5 x D (ALH Dhruv) -> 30 m",
                                                 "settlements": ranked}, indent=2), encoding="utf-8")
    return {"cut_off_any": len(ranked), "nearest_landing_km": {r["name"]: (r["landing_sites"][0]["dist_km"] if r["landing_sites"] else None) for r in ranked}}


def rescue_only(name: str):
    """Recompute rescue.json from a finished run's saved outputs (no downloads)."""
    out = PROJECT_ROOT / "results/space" / name
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    grid = data.make_grid(tuple(summary["bbox"]), summary["grid"]["res_m"])
    osm = json.loads((out / "osm_before.json").read_text(encoding="utf-8"))
    rd = lambda f: rasterio.open(out / f).read(1)  # noqa: E731
    deb = rd("debris_class.tif") if (out / "debris_class.tif").exists() else None
    ld = lambda f: json.loads((out / f).read_text(encoding="utf-8")) if (out / f).exists() else {}  # noqa: E731
    summary["rescue"] = rescue_step(out, grid, osm, rd("dem.tif"), rd("flood_class.tif"), flood.permanent_water(osm["water"], grid),
                                    deb, ld("cutoff.json"), ld("cutoff_debris.json"))
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary["rescue"], indent=1))


def run(name: str, bbox: tuple, event: pd.Timestamp, res=10.0) -> dict:
    out = PROJECT_ROOT / "results/space" / name
    out.mkdir(parents=True, exist_ok=True)
    t_start = time.time()
    grid = data.make_grid(bbox, res)
    print(f"grid {grid.width}x{grid.height} @ {res} m, {grid.crs}")
    pairs = data.s1_pairs(bbox, event)
    if not pairs:
        msg = ("No Sentinel-1 before/after pair on the same orbit within 12 days of the event for this area. "
               "Sentinel-1 revisits every 6-12 days: try a date a few days later, or a slightly larger area.")
        (out / "summary.json").write_text(json.dumps({"name": name, "bbox": bbox, "event_utc": str(event), "error": msg}, indent=2), encoding="utf-8")
        raise SystemExit("ERROR: " + msg)
    print("S1 pairs:", [(p["orbit"], p["state"], p["before_t"][:16], p["after_t"][:16]) for p in pairs])
    pairs_db = [(data.s1_db(p["before"], grid), data.s1_db(p["after"], grid)) for p in pairs]
    z = data.dem(grid)
    osm = data.osm_before(bbox, event)
    (out / "osm_before.json").write_text(json.dumps(osm), encoding="utf-8")
    perm = flood.permanent_water(osm["water"], grid)
    corr = flood.corridor(osm["waterways"], grid)
    chan = np.zeros((grid.height, grid.width), bool)       # the mapped drainage (pre-event OSM waterways)
    ww = [transform_geom("EPSG:4326", grid.crs, f["geometry"]) for f in osm["waterways"].get("features", []) if f.get("geometry")]
    if ww:
        chan = rasterize([(g, 1) for g in ww], out_shape=chan.shape, transform=grid.transform, all_touched=True, dtype="uint8").astype(bool)
    low = flood.hand(np.nan_to_num(z, nan=np.nanmax(z)), chan | perm) <= flood.HAND_MAX_M   # Twele et al. 2016 HAND rule
    save_tif(out / "hand_ok.tif", low.astype("uint8"), grid)
    cls, stats = flood.detect(pairs_db, z, perm, grid, [(p["after"]["geometry"], p["state"]) for p in pairs], corr)
    save_tif(out / "flood_class.tif", cls, grid)
    save_tif(out / "dem.tif", z.astype("float32"), grid)
    summary = {"name": name, "bbox": bbox, "event_utc": str(event), "grid": {"crs": grid.crs, "res_m": res, "w": grid.width, "h": grid.height},
               "s1_pairs": [{k: p[k] for k in ("orbit", "state", "before_t", "after_t")} | {"before_id": p["before"]["id"], "after_id": p["after"]["id"]} for p in pairs],
               "osm_snapshot": osm["_snapshot"], "osm_counts": {k: len(v.get("features", [])) for k, v in osm.items() if not k.startswith("_")},
               "flood": stats, "method": flood.__doc__.strip().splitlines()[0]}
    method = "rule baseline (UN-SPIDER + ESA layover/shadow + 200 m corridor)"
    if ai.available():   # AI model is the primary detector when weights exist; rule map kept for comparison
        save_tif(out / "flood_class_rule.tif", cls, grid)
        flood_any = np.zeros(cls.shape, bool)
        for p in pairs:
            post = (data.s1_db(p["after"], grid, "vv"), data.s1_db(p["after"], grid, "vh"))
            pre1 = (data.s1_db(p["before"], grid, "vv"), data.s1_db(p["before"], grid, "vh"))
            pre2 = (data.s1_db(p["before2"], grid, "vv"), data.s1_db(p["before2"], grid, "vh"))
            flood_any |= ai.predict(post, pre1, pre2, z) == 2
        stats["ai_flood_km2_all"] = round(float(flood_any.sum() * res * res / 1e6), 3)
        flood_any = flood.drop_small(flood_any & corr & low & ~perm)
        cls = np.where(perm, flood.PERMANENT, np.where(flood_any, flood.WATER, flood.NONE)).astype("uint8")
        stats["ai_flood_km2_corridor"] = round(float(flood_any.sum() * res * res / 1e6), 3)
        method = "AI U-Net (Kuro Siwo) within the 200 m river corridor"
        save_tif(out / "flood_class.tif", cls, grid)
        summary["flood"] = stats
    # Sentinel-2 when the sky is clear: new open water (MNDWI) joins the flood map; vegetated->barren change is
    # optical debris evidence. Cloudy areas are left to radar.
    try:
        s2 = optical.evidence(bbox, grid, event)
    except Exception as e:  # noqa: BLE001 - optical is optional; radar answer still stands
        s2 = {"meta": {"used": False, "reason": f"Sentinel-2 unavailable ({type(e).__name__})"}}
    summary["s2"] = s2["meta"]
    print("S2:", s2["meta"])
    if s2["meta"].get("used"):
        save_tif(out / "s2_clear.tif", s2["clear"].astype("uint8"), grid)
        s2w = flood.drop_small(s2["new_water"] & corr & low & ~perm)
        stats["s2_new_water_km2"] = round(float(s2w.sum() * res * res / 1e6), 3)
        stats["s2_added_km2"] = round(float((s2w & (cls == flood.NONE)).sum() * res * res / 1e6), 3)
        cls = np.where((cls == flood.NONE) & s2w, flood.WATER, cls).astype("uint8")
        save_tif(out / "flood_class.tif", cls, grid)
        method += " + Sentinel-2 MNDWI new water where clear"
        summary["flood"] = stats
    summary["detector"] = method
    dmg = impact.damage(osm, cls, grid)
    cut = impact.cut_off(osm, dmg, bbox)
    for layer in ("buildings", "roads", "bridges"):
        (out / f"{layer}_hit.geojson").write_text(json.dumps(dmg[layer]), encoding="utf-8")
    # secondary, low-confidence layer: debris / strong radar change from the rule baseline (the AI is trained on
    # floodwater only; debris flows such as Dharali are rough deposits, not water). Reported separately.
    rule_p = out / "flood_class_rule.tif"
    if rule_p.exists():
        with rasterio.open(rule_p) as src:
            rule = src.read(1)
        radar_d = flood.drop_small(rule == flood.DEBRIS)   # HAND not applied: debris flows run high on gorge walls
        opt_d = flood.drop_small(s2["debris"] & corr) if s2["meta"].get("used") else np.zeros_like(radar_d)
        # confidence: 1 = radar only, 2 = optical only, 3 = radar AND optical agree
        conf = (radar_d * 1 + opt_d * 2).astype("uint8")
        save_tif(out / "debris_conf.tif", conf, grid)
        deb = np.where(radar_d | opt_d, flood.DEBRIS, flood.NONE).astype("uint8")
        save_tif(out / "debris_class.tif", deb, grid)
        dmg_d = impact.damage(osm, deb, grid)
        cut_d = impact.cut_off(osm, dmg_d, bbox)
        for layer in ("buildings", "roads", "bridges"):
            (out / f"{layer}_debris.geojson").write_text(json.dumps(dmg_d[layer]), encoding="utf-8")
        (out / "cutoff_debris.json").write_text(json.dumps(cut_d, indent=2), encoding="utf-8")
        summary["debris_rule"] = {"km2": round(float((deb == flood.DEBRIS).sum() * res * res / 1e6), 3), "damage": dmg_d["counts"],
                                  "cutoff": cut_d.get("counts"), "note": "rule-based radar change (low confidence) plus Sentinel-2 vegetated-to-barren change where clear",
                                  "radar_km2": round(float(radar_d.sum() * res * res / 1e6), 3), "optical_km2": round(float(opt_d.sum() * res * res / 1e6), 3),
                                  "both_km2": round(float((radar_d & opt_d).sum() * res * res / 1e6), 3)}
    (out / "cutoff.json").write_text(json.dumps(cut, indent=2), encoding="utf-8")
    summary["rescue"] = rescue_step(out, grid, osm, z, cls, perm, deb if rule_p.exists() else None, cut, cut_d if rule_p.exists() else {})
    summary |= {"damage": dmg["counts"], "cutoff": {k: cut.get(k) for k in ("destination", "counts", "removed_segments")}}
    summary["runtime_s"] = round(time.time() - t_start, 1)
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"flood": summary["flood"], "damage": summary["damage"], "cutoff": summary["cutoff"]}, indent=1))
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--bbox", help="W,S,E,N")
    ap.add_argument("--date", help="event time UTC, e.g. '2025-08-05 08:15'")
    ap.add_argument("--res", type=float, default=10.0)
    ap.add_argument("--rescue-only", action="store_true", help="recompute rescue.json from saved outputs")
    a = ap.parse_args()
    if a.rescue_only:
        raise SystemExit(rescue_only(a.name))
    run(a.name, tuple(float(v) for v in a.bbox.split(",")), pd.Timestamp(a.date), a.res)
