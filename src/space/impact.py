"""Space mode — "What was damaged?" and "Who is cut off?" from the flood/debris map and pre-event OSM.

Damage: each pre-event OSM building / road / bridge is 'hit' if any flood or debris pixel of the class map falls on
it (buildings: footprint; lines: rasterised with all_touched). No buffer, no score — a direct overlay.
Roads and bridges are checked segment by segment (each pair of consecutive OSM vertices, sampled every half pixel):
a way counts as hit if any segment is, but only the hit segments are cut in the graph. A long highway is therefore not
removed end to end because one pixel touches it somewhere.
Cut-off: an undirected road graph is built from the pre-event OSM road lines (vertices shared by ways are junctions,
edge weight = length). Hit road and bridge segments are removed. Destinations are hospitals/clinics, else towns
/cities, else the points where roads leave the area of interest (connection to the outside world). A settlement
(OSM place node) is CUT OFF if it reached a destination before the flood and cannot after; for the others the
extra travel distance is reported.
"""
import math

import networkx as nx
import numpy as np
from rasterio.features import rasterize
from rasterio.warp import transform_geom

from src.space.data import Grid
from src.space.flood import DEBRIS, WATER


def _px_hit(geom_utm: dict, cls: np.ndarray, grid: Grid) -> bool:
    m = rasterize([geom_utm], out_shape=cls.shape, transform=grid.transform, fill=0, default_value=1, all_touched=True).astype(bool)
    return bool(np.isin(cls[m], (WATER, DEBRIS)).any())


def _parts(g: dict) -> list:
    return [g["coordinates"]] if g.get("type") == "LineString" else g.get("coordinates", []) if g.get("type") == "MultiLineString" else []


def _seg_hits(g_ll: dict, cls: np.ndarray, grid: Grid) -> list:
    """[(lon/lat a, lon/lat b)] of the vertex pairs whose line touches a flood/debris pixel."""
    bad = np.isin(cls, (WATER, DEBRIS))
    inv = ~grid.transform
    hits = []
    for line_ll, line in zip(_parts(g_ll), _parts(transform_geom("EPSG:4326", grid.crs, g_ll))):
        for (a_ll, b_ll), (a, b) in zip(zip(line_ll, line_ll[1:]), zip(line, line[1:])):
            n = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / (grid.res / 2)) + 1)
            xs, ys = np.linspace(a[0], b[0], n), np.linspace(a[1], b[1], n)
            c, r = inv * (xs, ys)
            r, c = np.floor(r).astype(int), np.floor(c).astype(int)
            ok = (r >= 0) & (r < cls.shape[0]) & (c >= 0) & (c < cls.shape[1])
            if bad[r[ok], c[ok]].any():
                hits.append(((round(a_ll[0], 6), round(a_ll[1], 6)), (round(b_ll[0], 6), round(b_ll[1], 6))))
    return hits


def damage(osm: dict, cls: np.ndarray, grid: Grid) -> dict:
    out, hit_edges = {}, set()
    for layer in ("buildings", "roads", "bridges"):
        feats = []
        for f in osm.get(layer, {}).get("features", []):
            if not f.get("geometry"):
                continue
            tags = f.get("properties", {})
            props = {"id": tags.get("@osmId"), "name": tags.get("name"), "kind": tags.get("highway") or tags.get("building")}
            if layer == "buildings":
                props["hit"] = _px_hit(transform_geom("EPSG:4326", grid.crs, f["geometry"]), cls, grid)
            else:
                segs = _seg_hits(f["geometry"], cls, grid)
                hit_edges |= {frozenset(s) for s in segs}
                props |= {"hit": bool(segs), "hit_parts": [[list(a), list(b)] for a, b in segs]}
            feats.append({"type": "Feature", "geometry": f["geometry"], "properties": props})
        out[layer] = {"type": "FeatureCollection", "features": feats}
    out["counts"] = {k: {"total": len(v["features"]), "hit": sum(f["properties"]["hit"] for f in v["features"])} for k, v in out.items()}
    out["_hit_edges"] = hit_edges
    return out


def _metres(a, b):
    k = math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot((a[0] - b[0]) * 111320 * k, (a[1] - b[1]) * 110540)


def road_graph(roads: dict, hit_edges: set) -> tuple[nx.Graph, nx.Graph]:
    """(graph before, graph after removing hit road/bridge segments). Nodes are rounded lon/lat vertices."""
    before, after = nx.Graph(), nx.Graph()
    for f in roads.get("features", []):
        g = f.get("geometry") or {}
        lines = [g["coordinates"]] if g.get("type") == "LineString" else g.get("coordinates", []) if g.get("type") == "MultiLineString" else []
        for line in lines:
            pts = [(round(x, 6), round(y, 6)) for x, y in line]
            for a, b in zip(pts, pts[1:]):
                w = _metres(a, b)
                before.add_edge(a, b, w=w)
                if frozenset((a, b)) not in hit_edges:
                    after.add_edge(a, b, w=w)
    after.add_nodes_from(before.nodes)
    return before, after


def cut_off(osm: dict, dmg: dict, bbox) -> dict:
    hit_edges = dmg.get("_hit_edges", set())
    G0, G1 = road_graph(osm.get("roads", {}), hit_edges)
    if G0.number_of_nodes() == 0:
        return {"settlements": [], "note": "no mapped roads"}
    nodes = np.array(list(G0.nodes))

    def snap(lon, lat):
        k = math.cos(math.radians(lat))
        i = int(np.argmin(((nodes[:, 0] - lon) * k) ** 2 + (nodes[:, 1] - lat) ** 2))
        return tuple(nodes[i]), _metres((lon, lat), tuple(nodes[i]))

    def pt(f):
        c = f["geometry"]["coordinates"]
        return c if f["geometry"]["type"] == "Point" else np.mean(np.array(c[0] if f["geometry"]["type"] == "Polygon" else c), axis=0)

    hosp = [pt(f) for f in osm.get("hospitals", {}).get("features", []) if f.get("geometry")]
    towns = [pt(f) for f in osm.get("places", {}).get("features", []) if f.get("properties", {}).get("place") in ("city", "town")]
    w, s, e, n = bbox
    edge_nodes = [v for v in G0.nodes if min(v[0] - w, e - v[0], v[1] - s, n - v[1]) < 0.002]  # roads leaving the AOI
    kind = "hospital" if hosp else "town" if towns else "AOI exit"
    dests = [snap(*p)[0] for p in hosp] if hosp else [snap(*p)[0] for p in towns] if towns else edge_nodes

    def dist(G, src):
        srcs = set(dests) & set(G.nodes)
        if not srcs:
            return None
        try:
            return nx.multi_source_dijkstra(G, srcs, target=src, weight="w")[0]
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    rows = []
    for f in osm.get("places", {}).get("features", []):
        if not f.get("geometry"):
            continue
        lon, lat = pt(f)
        node, gap = snap(lon, lat)
        d0, d1 = dist(G0, node), dist(G1, node)
        tags = f.get("properties", {})
        rows.append({"name": tags.get("name:en") or tags.get("name"), "place": tags.get("place"), "lon": round(float(lon), 5), "lat": round(float(lat), 5),
                     "snap_m": round(gap), "before_km": None if d0 is None else round(d0 / 1000, 2), "after_km": None if d1 is None else round(d1 / 1000, 2),
                     "status": "not connected before" if d0 is None else "CUT OFF" if d1 is None else ("longer route" if d1 > d0 * 1.05 + 50 else "connected")})
    return {"destination": kind, "settlements": rows, "removed_segments": len(hit_edges),
            "counts": {k: sum(r["status"] == k for r in rows) for k in ("CUT OFF", "longer route", "connected", "not connected before")}}
