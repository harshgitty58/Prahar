"""Check a Space-mode run against Copernicus EMS rapid-mapping vectors (CHECKING ONLY - never an input).
Pixel scores of the AI-water layer, the debris layer and their union against EMS 'observed event' polygons,
inside the EMS AOIs only (outside them EMS made no statement), plus building- and road-level agreement with the
EMS damage grading. Writes results/space/<name>/emsr_check.json + emsr_check.png.
Run: python scripts/check_emsr.py --name trishuli --emsr data/external/emsr927 --aois 1,2
"""
import argparse
import glob
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.warp import transform_geom
from scipy.ndimage import binary_dilation
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
DAMAGED = {"Destroyed", "Damaged", "Possibly damaged"}


def load(pattern, crs):
    feats = []
    for f in sorted(glob.glob(pattern)):
        for x in [x for x in json.load(open(f, encoding="utf-8"))["features"] if x.get("geometry")]:
            x["geometry"] = transform_geom("EPSG:4326", crs, x["geometry"])
            feats.append(x)
    return feats


def scores(pred, truth, m):
    p, t = pred[m], truth[m]
    tp, fp, fn = int((p & t).sum()), int((p & ~t).sum()), int((~p & t).sum())
    P = tp / (tp + fp) if tp + fp else 0.0
    R = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": round(P, 3), "recall": round(R, 3), "f1": round(2 * P * R / (P + R), 3) if P + R else 0.0,
            "iou": round(tp / (tp + fp + fn), 3) if tp + fp + fn else 0.0, "tp_px": tp, "fp_px": fp, "fn_px": fn}


def obj_agree(feats, hit_mask, grid_t, shape_):
    """Per EMS object: truth = graded damaged; predicted = touches a detected pixel (1-pixel tolerance)."""
    tp = fp = fn = tn = 0
    for x in feats:
        r = rasterize([(x["geometry"], 1)], out_shape=shape_, transform=grid_t, all_touched=True, dtype="uint8").astype(bool)
        if not r.any():
            continue
        pred = bool((r & hit_mask).any())
        true = x["properties"].get("damage_gra") in DAMAGED
        tp += pred and true; fp += pred and not true; fn += (not pred) and true; tn += (not pred) and not true
    P = tp / (tp + fp) if tp + fp else 0.0
    R = tp / (tp + fn) if tp + fn else 0.0
    return {"n": tp + fp + fn + tn, "ems_damaged": tp + fn, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(P, 3), "recall": round(R, 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--emsr", required=True)
    ap.add_argument("--aois", default="1,2")
    ap.add_argument("--aoi-json", default=None, help="EMS activation JSON (with aois[].extent WKT)")
    a = ap.parse_args()
    out = ROOT / "results/space" / a.name
    emsr = ROOT / a.emsr
    with rasterio.open(out / "flood_class.tif") as s:
        ai_cls, T, crs, shp = s.read(1), s.transform, s.crs.to_string(), (s.height, s.width)
    with rasterio.open(out / "debris_class.tif") as s:
        deb = s.read(1) == 2
    with rasterio.open(out / "dem.tif") as s:
        z = s.read(1)
    water = ai_cls == 1
    aoi_ids = [f"AOI{int(i):02d}" for i in a.aois.split(",")]
    aois = json.load(open(emsr / "aois.geojson", encoding="utf-8"))["features"]
    aois = [x for x in aois if x["properties"]["aoi"] in aoi_ids]
    m = rasterize([(transform_geom("EPSG:4326", crs, x["geometry"]), 1) for x in aois], out_shape=shp, transform=T, dtype="uint8").astype(bool)
    ev = [x for i in aoi_ids for x in load(str(emsr / f"EMSR*_{i}_GRA_PRODUCT_observedEventA_*.json"), crs)]
    truth = rasterize([(x["geometry"], 1) for x in ev], out_shape=shp, transform=T, dtype="uint8").astype(bool)
    px_km2 = abs(T.a * T.e) / 1e6
    res = {"event": a.name, "ems": sorted({x["properties"].get("obj_desc", "") for x in ev}), "aois": aoi_ids,
           "aoi_km2": round(float(m.sum() * px_km2), 3), "ems_event_km2": round(float((truth & m).sum() * px_km2), 3),
           "note": "Copernicus EMS vectors used ONLY to check the output, never as an input."}
    layers = {"ai_water": water, "debris": deb, "union": water | deb}
    if (out / "debris_conf.tif").exists():   # ablation: which sensor found the debris (1 radar, 2 optical, 3 both)
        with rasterio.open(out / "debris_conf.tif") as s_:
            conf = s_.read(1)
        layers |= {"debris_radar_only_input": (conf & 1) > 0, "debris_optical_only_input": (conf & 2) > 0}
    res["pixel"] = {k: scores(v, truth, m) | {"km2_in_aoi": round(float((v & m).sum() * px_km2), 3)} for k, v in layers.items()}
    # 1-pixel tolerance for object agreement (EMS points sit on roofs; OSM/S1 co-registration ~ 1 pixel)
    blds = [x for i in aoi_ids for x in load(str(emsr / f"EMSR*_{i}_GRA_PRODUCT_builtUpP_*.json"), crs)]
    roads = [x for i in aoi_ids for x in load(str(emsr / f"EMSR*_{i}_GRA_PRODUCT_transportationL_*.json"), crs)]
    res["buildings"] = {k: obj_agree(blds, binary_dilation(v, iterations=1), T, shp) for k, v in layers.items()}
    res["roads"] = {k: obj_agree(roads, binary_dilation(v, iterations=1), T, shp) for k, v in layers.items()}
    # EMS grades only damaged buildings (no 'not damaged' class), so object precision comes from our side: share of
    # OSM buildings we flag inside the AOIs that lie within 25 m of an EMS-damaged building
    from shapely.strtree import STRtree
    from shapely.ops import unary_union
    dmg_pts = [shape(b["geometry"]).centroid for b in blds if b["properties"].get("damage_gra") in DAMAGED]
    tree, aoi_u = STRtree(dmg_pts), unary_union([shape(transform_geom("EPSG:4326", crs, x["geometry"])) for x in aois])
    flagged = {}
    for k, f in (("ai_water", "buildings_hit.geojson"), ("debris", "buildings_debris.geojson")):
        fc = json.load(open(out / f, encoding="utf-8"))["features"]
        flagged[k] = {i: shape(transform_geom("EPSG:4326", crs, x["geometry"])) for i, x in enumerate(fc) if x["properties"].get("hit")}
    flagged["union"] = list(flagged["ai_water"].values()) + list(flagged["debris"].values())
    flagged["ai_water"], flagged["debris"] = list(flagged["ai_water"].values()), list(flagged["debris"].values())
    for k, gs in flagged.items():
        gs = [g for g in gs if g.intersects(aoi_u)]
        near = sum(len(tree.query(g, predicate="dwithin", distance=25)) > 0 for g in gs) if dmg_pts else 0
        res["buildings"][k] |= {"osm_flagged_in_aoi": len(gs), "osm_flagged_near_ems_damage": near,
                                "osm_precision": round(near / len(gs), 3) if gs else None}
    if (out / "s2_clear.tif").exists():      # how much of what we missed was under cloud in the post-event Sentinel-2
        with rasterio.open(out / "s2_clear.tif") as s_:
            clr = s_.read(1).astype(bool)
        fn = truth & m & ~layers["union"]
        res["missed_under_cloud_share"] = round(float((fn & ~clr).sum() / max(fn.sum(), 1)), 3)
        res["ems_event_clear_share"] = round(float((truth & m & clr).sum() / max((truth & m).sum(), 1)), 3)
        cm = m & clr
        res["pixel_where_s2_clear"] = {k: scores(v, truth, cm) for k, v in layers.items()}
    (out / "emsr_check.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=1))

    # error map per AOI: green = agree, red = we flagged / EMS did not, blue = EMS mapped / we missed
    pred = layers["union"]
    layers = {k: v for k, v in layers.items()}
    fig, axs = plt.subplots(1, len(aois), figsize=(6 * len(aois), 7))
    axs = np.atleast_1d(axs)
    gy, gx = np.gradient(z.astype("float32"), 10)
    hs = np.clip(0.5 + 0.5 * (gx - gy) / np.hypot(gx, gy).clip(1e-3) * np.tanh(np.hypot(gx, gy)), 0, 1)
    for ax, x in zip(axs, aois):
        mi = rasterize([(transform_geom("EPSG:4326", crs, x["geometry"]), 1)], out_shape=shp, transform=T, dtype="uint8").astype(bool)
        rows, cols = np.where(mi)
        r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
        rgb = np.dstack([hs] * 3) * 0.75
        for msk, col in (((pred & truth), (0.1, 0.8, 0.2)), ((pred & ~truth), (0.9, 0.15, 0.1)), ((~pred & truth), (0.15, 0.4, 1.0))):
            rgb[msk & mi] = col
        rgb[~mi] *= 0.4
        ax.imshow(rgb[r0:r1, c0:c1])
        for b in blds:
            if b["properties"].get("damage_gra") in DAMAGED:
                c = shape(b["geometry"]).centroid
                cc, rr = ~T * (c.x, c.y)
                if r0 <= rr < r1 and c0 <= cc < c1:
                    ax.plot(cc - c0, rr - r0, "o", ms=2.5, mfc="yellow", mec="black", mew=0.3)
        ax.set_title(f"{x['properties']['aoi']} {x['properties']['name']}", fontsize=11)
        ax.axis("off")
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    fig.legend(handles=[Patch(color=(0.1, 0.8, 0.2), label="PRAHAR and EMS agree"), Patch(color=(0.9, 0.15, 0.1), label="PRAHAR only (false alarm?)"),
                        Patch(color=(0.15, 0.4, 1.0), label="EMS only (missed)"),
                        Line2D([], [], marker="o", ls="", mfc="yellow", mec="black", label="EMS damaged building")],
               loc="lower center", ncol=4, fontsize=9, frameon=False)
    u = res["pixel"]["union"]
    fig.suptitle(f"{a.name}: PRAHAR (AI/Sentinel-2 water + radar/optical debris) vs Copernicus EMS (check only) - IoU {u['iou']}, P {u['precision']}, R {u['recall']}", fontsize=11)
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    fig.savefig(out / "emsr_check.png", dpi=150)
    print("saved", out / "emsr_check.png")


if __name__ == "__main__":
    main()
