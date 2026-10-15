"""Rescue add-ons for cut-off settlements, computed only from allowed inputs (Copernicus DEM, pre-event OSM, our maps).

people_at(): pre-event OSM buildings assigned to their nearest mapped settlement (within MAX_ASSIGN_M), so the sitrep can
             rank cut-off places by size ("who first").
landing_zones(): candidate helicopter landing sites near each cut-off settlement, following ICAO Annex 14 Vol II
             (Heliports): FATO mean slope <= 3 %, no local slope > 5 %, FATO side >= 1.5 x D. For the ALH Dhruv used in
             Himalayan rescue, D = 15.9 m -> 24 m, so a 30 x 30 m dry, open patch is required. Excluded: flooded or debris
             pixels, permanent water, the mapped river channel and any pre-event OSM building.
These are map candidates only: obstacles (wires, trees), surface and approach paths must be checked by the crew.
"""
import numpy as np
from rasterio.features import rasterize
from rasterio.warp import transform_geom
from scipy import ndimage
from shapely.geometry import shape

FATO_M = 30.0                       # >= 1.5 x D (ALH Dhruv D = 15.9 m), rounded up to the grid
MEAN_SLOPE_PCT, LOCAL_SLOPE_PCT = 3.0, 5.0
MAX_ASSIGN_M = 2000                 # a building further than this from every mapped place is left unassigned
N_SITES = 3


def _xy(grid, lon, lat):
    g = transform_geom("EPSG:4326", grid.crs, {"type": "Point", "coordinates": [lon, lat]})
    return g["coordinates"]


def people_at(osm: dict, settlements: list, grid) -> dict:
    """{settlement name: number of pre-event OSM buildings nearest to it}."""
    if not settlements:
        return {}
    pts = np.array([_xy(grid, s["lon"], s["lat"]) for s in settlements])
    counts = np.zeros(len(pts), int)
    for f in osm.get("buildings", {}).get("features", []):
        if not f.get("geometry"):
            continue
        c = shape(transform_geom("EPSG:4326", grid.crs, f["geometry"])).centroid
        d = np.hypot(pts[:, 0] - c.x, pts[:, 1] - c.y)
        if d.min() <= MAX_ASSIGN_M:
            counts[d.argmin()] += 1
    return {s["name"]: int(n) for s, n in zip(settlements, counts)}


def landing_zones(dem, grid, blocked: np.ndarray, osm: dict, settlements: list) -> list:
    """Nearest N_SITES candidate landing patches for each settlement given (lon/lat dicts with 'name')."""
    res = grid.res
    gy, gx = np.gradient(dem.astype("float32"), res)
    slope = 100 * np.hypot(gx, gy)
    k = max(1, int(round(FATO_M / res)))
    bld = np.zeros(dem.shape, bool)
    geoms = [transform_geom("EPSG:4326", grid.crs, f["geometry"]) for f in osm.get("buildings", {}).get("features", []) if f.get("geometry")]
    if geoms:
        bld = rasterize([(g, 1) for g in geoms], out_shape=dem.shape, transform=grid.transform, all_touched=True, dtype="uint8").astype(bool)
    ok = ~blocked & ~bld & np.isfinite(slope)
    ok &= ndimage.uniform_filter(np.nan_to_num(slope, nan=99), k) <= MEAN_SLOPE_PCT
    ok &= ndimage.maximum_filter(np.nan_to_num(slope, nan=99), k) <= LOCAL_SLOPE_PCT
    ok = ndimage.minimum_filter(ok.astype("uint8"), k).astype(bool)          # whole k x k FATO must qualify
    lab, n = ndimage.label(ok)
    if n == 0:
        return [{"settlement": s["name"], "sites": []} for s in settlements]
    idx = np.arange(1, n + 1)
    cy, cx = np.array(ndimage.center_of_mass(ok, lab, idx)).T
    area = ndimage.sum(ok, lab, idx) * res * res
    xs, ys = grid.transform * (cx + 0.5, cy + 0.5)
    out = []
    for s in settlements:
        x0, y0 = _xy(grid, s["lon"], s["lat"])
        d = np.hypot(xs - x0, ys - y0)
        sites = []
        for i in np.argsort(d)[:N_SITES]:
            lon, lat = transform_geom(grid.crs, "EPSG:4326", {"type": "Point", "coordinates": [float(xs[i]), float(ys[i])]})["coordinates"]
            sites.append({"lon": round(lon, 5), "lat": round(lat, 5), "dist_km": round(float(d[i]) / 1000, 2), "flat_m2": int(area[i])})
        out.append({"settlement": s["name"], "sites": sites})
    return out
