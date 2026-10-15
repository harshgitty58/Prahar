"""Space mode — "Where did the flood hit?" Sentinel-1 change detection after the UN-SPIDER Recommended Practice.

UN-SPIDER (UNOOSA) Recommended Practice: Flood Mapping with Google Earth Engine (Sentinel-1):
  VH backscatter in dB, smoothed with a 50 m circular focal mean; difference = after / before (dB ratio);
  flooded where difference > 1.25; permanent water masked; slope > 5 % masked;
  pixels connected to 8 or fewer neighbours removed.
  https://un-spider.org/advisory-support/recommended-practices/recommended-practice-google-earth-engine-flood-mapping
Adaptations required by the Track B input rules (stated, not tuned):
  * permanent water = pre-event OSM water areas (JRC Global Surface Water is not an allowed input);
  * mountains: the 5 % slope mask removes ~99.6 % of a Himalayan valley (Dharali test), so it is replaced by the
    standard SAR geometry masks (ESA, e.g. SNAP layover/shadow masking), computed per orbit from Copernicus GLO-30:
    layover where terrain facing the radar is steeper than the local incidence angle; shadow where terrain facing
    away is steeper than 90° - incidence. Incidence spans Sentinel-1 IW's published 29.1°-46.0° across the swath
    (interpolated from the scene footprint); look direction = right of the flight heading. Only local (active)
    layover/shadow is modelled — passive shadow cast by distant ridges is a stated limitation. The UN-SPIDER slope
    mask is still computed and reported for comparison (stats["unspider_slope_masked_km2"]).
  * "possible debris / strong change": the mirror condition after/before < 1/1.25 (backscatter rose — rough deposits),
    same masks. No official debris rule exists; it is reported separately from water.
Analysis corridor: detections are kept only within CORRIDOR_M of a pre-event OSM river/stream/canal/drain — the
  Uttarakhand High Court (Aug 2013) 200 m river no-construction corridor, the official flood-prone strip used for
  buildings too. In steep monsoon terrain a 12-day S1 pair otherwise flags whole wet hillsides (Dharali test).
Each same-orbit pair is processed independently; a pixel is flagged if any pair flags it (orbits see different slopes).
"""
import numpy as np
from rasterio.features import rasterize
from scipy import ndimage

from src.space.data import Grid, slope_percent

DIFF_THRESHOLD = 1.25      # UN-SPIDER
SMOOTH_RADIUS_M = 50.0     # UN-SPIDER
SLOPE_MAX_PCT = 5.0        # UN-SPIDER (reported for comparison only)
CORRIDOR_M = 200.0         # Uttarakhand High Court 2013 river corridor
IW_INC_DEG = (29.1, 46.0)  # Sentinel-1 IW incidence-angle range (ESA Sentinel-1 user guide)
MIN_NEIGHBOURS = 8         # UN-SPIDER: remove pixels connected to <= 8 neighbours
NONE, WATER, DEBRIS, PERMANENT = 0, 1, 2, 3


def smooth(db: np.ndarray, res: float) -> np.ndarray:
    r = int(round(SMOOTH_RADIUS_M / res))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    k = (xx ** 2 + yy ** 2 <= r * r).astype("float32")
    valid = np.isfinite(db).astype("float32")
    num = ndimage.convolve(np.nan_to_num(db), k, mode="nearest")
    den = ndimage.convolve(valid, k, mode="nearest")
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / den, np.nan).astype("float32")


HAND_MAX_M = 15.0   # Twele et al. (2016), Int. J. Remote Sensing 37(13): pixels > 15 m above the nearest drainage excluded


def hand(dem: np.ndarray, drainage: np.ndarray) -> np.ndarray:
    """Height Above Nearest Drainage (approximation: nearest drainage pixel by distance, not along the flow path).
    drainage = pre-event OSM waterways + permanent water rasterised on the grid."""
    if not drainage.any():
        return np.zeros_like(dem)
    _, (ri, ci) = ndimage.distance_transform_edt(~drainage, return_indices=True)
    return dem - dem[ri, ci]


def drop_small(mask: np.ndarray) -> np.ndarray:
    lab, n = ndimage.label(mask, structure=np.ones((3, 3)))
    if n == 0:
        return mask
    sizes = ndimage.sum(mask, lab, index=np.arange(1, n + 1))
    keep = np.zeros(n + 1, bool)
    keep[1:] = sizes > MIN_NEIGHBOURS + 1  # a pixel plus <= 8 connected neighbours is removed
    return keep[lab]


def permanent_water(osm_water: dict, grid: Grid) -> np.ndarray:
    from rasterio.warp import transform_geom
    geoms = [transform_geom("EPSG:4326", grid.crs, f["geometry"]) for f in osm_water.get("features", []) if f.get("geometry")]
    if not geoms:
        return np.zeros((grid.height, grid.width), bool)
    return rasterize(geoms, out_shape=(grid.height, grid.width), transform=grid.transform, fill=0, default_value=1).astype(bool)


def layover_shadow(dem: np.ndarray, grid: Grid, footprint: dict, orbit_state: str) -> np.ndarray:
    """Local SAR layover/shadow mask for one acquisition geometry (True = radar cannot see this pixel properly)."""
    from rasterio.warp import transform_geom
    ring = np.array(transform_geom("EPSG:4326", grid.crs, footprint)["coordinates"][0][:-1], float)
    c = ring.mean(0)
    _, _, vt = np.linalg.svd(ring - c)
    along = vt[0] if (vt[0][1] > 0) == (orbit_state == "ascending") else -vt[0]   # flight direction (N for ascending)
    right = np.array([along[1], -along[0]])                                         # right-looking: away from the track
    s = (ring - c) @ right
    rows, cols = np.mgrid[0:grid.height, 0:grid.width]
    x = grid.transform.c + (cols + 0.5) * grid.transform.a
    y = grid.transform.f + (rows + 0.5) * grid.transform.e
    f = np.clip((((x - c[0]) * right[0] + (y - c[1]) * right[1]) - s.min()) / (s.max() - s.min()), 0, 1)
    inc = np.radians(IW_INC_DEG[0] + f * (IW_INC_DEG[1] - IW_INC_DEG[0]))
    gy, gx = np.gradient(dem, grid.res)          # gy along rows (southward), gx eastward
    dz_dr = gx * right[0] + (-gy) * right[1]     # elevation change per metre moving away from the sensor
    tilt = np.arctan(np.abs(dz_dr))
    layover = (dz_dr < 0) & (tilt > inc)          # slope faces the radar, steeper than incidence
    shadow = (dz_dr > 0) & (tilt > np.pi / 2 - inc)  # slope faces away, steeper than the grazing angle
    return layover | shadow


def corridor(osm_waterways: dict, grid: Grid) -> np.ndarray:
    """True within CORRIDOR_M of any pre-event mapped waterway line."""
    from rasterio.warp import transform_geom
    lines = [transform_geom("EPSG:4326", grid.crs, f["geometry"]) for f in osm_waterways.get("features", []) if f.get("geometry")]
    if not lines:
        return np.ones((grid.height, grid.width), bool)
    on = rasterize(lines, out_shape=(grid.height, grid.width), transform=grid.transform, fill=0, default_value=1, all_touched=True).astype(bool)
    return ndimage.distance_transform_edt(~on) * grid.res <= CORRIDOR_M


def detect(pairs_db: list[tuple[np.ndarray, np.ndarray]], dem: np.ndarray, perm: np.ndarray, grid: Grid,
           geoms: list[tuple[dict, str]] | None = None, corr: np.ndarray | None = None) -> tuple[np.ndarray, dict]:
    """pairs_db: [(before_db, after_db), ...] on the grid; geoms: [(footprint GeoJSON, orbit_state), ...] per pair.
    Returns (class map, stats)."""
    steep = slope_percent(dem, grid.res) > SLOPE_MAX_PCT
    water, debris, seen = np.zeros(perm.shape, bool), np.zeros(perm.shape, bool), np.zeros(perm.shape, bool)
    hidden_all = np.ones(perm.shape, bool)
    for k, (before, after) in enumerate(pairs_db):
        b, a = smooth(before, grid.res), smooth(after, grid.res)
        hidden = layover_shadow(dem, grid, *geoms[k]) if geoms else steep
        hidden_all &= hidden
        ok = np.isfinite(a) & np.isfinite(b) & (b < 0) & ~hidden
        with np.errstate(invalid="ignore", divide="ignore"):
            diff = np.where(ok, a / b, np.nan)
        seen |= ok
        water |= ok & (diff > DIFF_THRESHOLD)
        debris |= ok & (diff < 1 / DIFF_THRESHOLD)
    corr = np.ones(perm.shape, bool) if corr is None else corr
    valid = seen & ~perm & corr
    water = drop_small(water & valid)
    debris = drop_small(debris & valid & ~water)
    cls = np.full(perm.shape, NONE, "uint8")
    cls[debris], cls[water], cls[perm] = DEBRIS, WATER, PERMANENT
    px_km2 = (grid.res ** 2) / 1e6
    stats = {"water_km2": round(float(water.sum() * px_km2), 3), "debris_km2": round(float(debris.sum() * px_km2), 3),
             "analysable_km2": round(float(valid.sum() * px_km2), 3), "hidden_all_orbits_km2": round(float(hidden_all.sum() * px_km2), 3),
             "unspider_slope_masked_km2": round(float(steep.sum() * px_km2), 3),
             "permanent_water_km2": round(float(perm.sum() * px_km2), 3), "pairs": len(pairs_db), "corridor_km2": round(float(corr.sum() * px_km2), 3)}
    return cls, stats
