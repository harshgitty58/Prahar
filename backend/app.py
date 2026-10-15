"""
PRAHAR API (FastAPI).

  uvicorn backend.app:app --port 8000          (dev: the web app proxies /api → here, see web/vite.config.ts)

Latency design
- everything is loaded once at startup (model, calibration tables, station states, exported JSON) — no disk I/O per request
- JSON payloads are pre-serialised bytes with a content hash ETag → repeat requests return 304 with no body
- GZip for responses > 1 KB; long Cache-Control for immutable building tiles
- /predict uses O(1) incremental features + lookup-table calibration (backend/inference.py)
- every response carries X-Process-Time-ms so latency is measured, not assumed
"""
import asyncio
import hashlib
import json
import time
from pathlib import Path

import httpx
import pandas as pd
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field

from backend.inference import Engine

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "web/public/data"
RESULTS = ROOT / "results"
EXTERNAL = {
    "carto_style": "https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json",
    "carto_glyphs": "https://tiles.basemaps.cartocdn.com/fonts/Montserrat%20Medium/0-255.pbf",
    "esri_imagery": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/8/105/183",
    "esri_labels": "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/8/105/183",
    "aws_terrain_dem": "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/8/183/105.png",
    "opentopomap": "https://a.tile.opentopomap.org/8/183/105.png",
    "overpass_main": "https://overpass-api.de/api/status",
    "overpass_private_coffee": "https://overpass.private.coffee/api/status",
    "ms_footprints_index": "https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv",
    "google_fonts": "https://fonts.googleapis.com/css2?family=Anton&display=swap",
}

app = FastAPI(title="PRAHAR API", version="1.0")
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STATE: dict = {}


class Blob:
    """Pre-serialised payload + ETag."""
    def __init__(self, body: bytes, media: str = "application/json"):
        self.body, self.media, self.etag = body, media, '"' + hashlib.md5(body).hexdigest()[:16] + '"'


def _blob(path: Path) -> Blob:
    return Blob(path.read_bytes(), "application/geo+json" if path.suffix == ".geojson" else "application/json")


def load_all():
    t0 = time.perf_counter()
    blobs = {p.stem: _blob(p) for p in DATA.glob("*.json")} | {p.stem: _blob(p) for p in DATA.glob("*.geojson")}
    # metrics: serve the exported, NaN-free web/public/data/metrics.json (the raw results file contained bare NaN,
    # which browsers reject as JSON, so the Metrics page was blank in API mode)
    STATE.update(blobs=blobs, tiles={}, engine=Engine(), loaded_at=time.time())
    STATE["startup_ms"] = round((time.perf_counter() - t0) * 1000, 1)


@app.on_event("startup")
def _startup():
    load_all()


@app.middleware("http")
async def timing(request: Request, call_next):
    t0 = time.perf_counter()
    resp = await call_next(request)
    resp.headers["X-Process-Time-ms"] = f"{(time.perf_counter() - t0) * 1000:.2f}"
    return resp


def send(blob: Blob, request: Request, cache: str = "no-cache") -> Response:
    if request.headers.get("if-none-match") == blob.etag:
        return Response(status_code=304, headers={"ETag": blob.etag, "Cache-Control": cache})
    return Response(blob.body, media_type=blob.media, headers={"ETag": blob.etag, "Cache-Control": cache})


def blob_or_404(name: str) -> Blob:
    b = STATE["blobs"].get(name)
    if b is None:
        raise HTTPException(404, f"{name} not exported — run scripts/run_all.py")
    return b


# ---------------- health -----------------------------------------------------------------------------------------
@app.get("/health")
def health():
    e = STATE["engine"]
    return {"status": "ok", "startup_ms": STATE["startup_ms"], "model_features": len(e.features),
            "stations": len(e.static), "datasets": sorted(STATE["blobs"]), "loaded_at": STATE["loaded_at"]}


_ext_cache: dict = {}


@app.get("/health/external")
async def health_external():
    """Probe every third-party service the platform depends on (cached 60 s)."""
    if _ext_cache.get("t", 0) > time.time() - 60:
        return _ext_cache["v"]

    async def probe(client, name, url):
        t0 = time.perf_counter()
        try:
            r = await client.get(url, headers={"User-Agent": "PRAHAR-health/1.0", "Range": "bytes=0-2047"})
            ok = r.status_code < 400
            return {"name": name, "ok": ok, "status": r.status_code, "ms": round((time.perf_counter() - t0) * 1000)}
        except Exception as ex:  # noqa: BLE001
            return {"name": name, "ok": False, "status": None, "ms": round((time.perf_counter() - t0) * 1000), "error": type(ex).__name__}

    async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
        res = await asyncio.gather(*(probe(client, n, u) for n, u in EXTERNAL.items()))
    v = {"checked_at": time.time(), "services": res, "ok": sum(r["ok"] for r in res), "total": len(res)}
    _ext_cache.update(t=time.time(), v=v)
    return v


# ---------------- data (1:1 with the static JSON files the frontend already reads) ------------------------------
@app.get("/data/{name}")
def data(name: str, request: Request):
    return send(blob_or_404(name.removesuffix(".json").removesuffix(".geojson")), request)


@app.get("/stations")
def stations(request: Request):
    return send(blob_or_404("stations"), request)


@app.get("/risk/snapshot")
def snapshot(request: Request):
    return send(blob_or_404("snapshot"), request)


@app.get("/risk/timeline")
def timeline(request: Request):
    return send(blob_or_404("timeline"), request)


@app.get("/model/summary")
def model_summary(request: Request):
    return send(blob_or_404("model"), request)


@app.get("/metrics")
def metrics(request: Request):
    return send(blob_or_404("metrics"), request)


@app.get("/events")
def events(request: Request):
    return send(blob_or_404("events"), request)


@app.get("/impact/summary")
def impact_summary(request: Request):
    return send(blob_or_404("impact"), request)


@app.get("/impact/tiles/index")
def tiles_index(request: Request):
    p = DATA / "bld/index.json"
    if not p.exists():
        raise HTTPException(404, "tiles not built — run scripts/build_building_tiles.py")
    return send(STATE["tiles"].setdefault("index", _blob(p)), request)


@app.get("/impact/tiles/{z}/{x}/{y}")
def tile(z: int, x: int, y: int, request: Request):
    key = f"{z}/{x}/{y}"
    if key not in STATE["tiles"]:
        p = DATA / "bld" / str(z) / str(x) / f"{y}.json"
        if not p.exists():
            return Response(b'{"type":"FeatureCollection","features":[]}', media_type="application/geo+json")
        STATE["tiles"][key] = _blob(p)  # LRU not needed: < 100 tiles
    return send(STATE["tiles"][key], request, cache="public, max-age=86400")


@app.get("/landmarks")
def landmarks(request: Request):
    return send(blob_or_404("landmarks"), request)


# ---------------- live inference ---------------------------------------------------------------------------------
class Reading(BaseModel):
    datetime: str
    rain_mm: float = Field(ge=0, le=150)


class PredictIn(BaseModel):
    station: str
    readings: list[Reading] = []
    overrides: dict[str, float] | None = None


@app.post("/predict")
def predict(body: PredictIn):
    e = STATE["engine"]
    try:
        t0 = time.perf_counter()
        out = e.predict(body.station, [r.model_dump() for r in body.readings], body.overrides)
        out["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        return out
    except KeyError:
        raise HTTPException(404, f"unknown or quarantined station {body.station!r}")


@app.post("/predict/scenario")
def scenario(body: PredictIn):
    """What-if: evaluate overrides (e.g. rain_24h=120) without mutating the station's live state."""
    e = STATE["engine"]
    if body.station not in e.static.index:
        raise HTTPException(404, body.station)
    st = e.states.get(body.station) or e.warm_station(body.station)
    row = {**e.static.loc[body.station].to_dict(), **st.features(), **(body.overrides or {}), "station": body.station}
    r = e.score(pd.DataFrame([row])).iloc[0]
    return {k: (v.item() if hasattr(v, "item") else v) for k, v in
            r[["station", "p_calibrated", "confidence", "cp_set_90", "tier", "tier_ml", "tier_rain", "trigger", "rain_24h"]].items()}


@app.post("/admin/reload")
def reload():
    load_all()
    return {"reloaded": True, "startup_ms": STATE["startup_ms"]}


# ---------------- Space mode (Track B): run the satellite pipeline for any area + date ---------------------------
import re  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import threading  # noqa: E402
import uuid  # noqa: E402

JOBS: dict = {}
STAGES = [("grid", "Preparing the map grid"), ("S1 pairs", "Found Sentinel-1 before/after pairs"), ("S2:", "Sentinel-2 checked"),
          ('"flood"', "Damage and cut-off computed"), ("Situation report", "Situation report written"), ("space_", "Published to the dashboard")]


class SpaceRun(BaseModel):
    bbox: list[float] = Field(..., min_length=4, max_length=4, description="W,S,E,N in WGS84")
    date: str = Field(..., description="event time UTC, e.g. 2026-08-25 22:00")
    name: str | None = None
    res: float = Field(10.0, ge=10.0, le=30.0)


def _space_job(jid: str, req: SpaceRun):
    j = JOBS[jid]
    log = RESULTS / "space" / f"{j['name']}_run.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    cmds = [[sys.executable, "-u", "-m", "src.space.run", "--name", j["name"], "--bbox", ",".join(map(str, req.bbox)), "--date", req.date, "--res", str(req.res)],
            [sys.executable, "-m", "src.space.report", "--name", j["name"]],
            [sys.executable, "scripts/export_space.py", "--name", j["name"]]]
    with open(log, "w", encoding="utf-8") as fh:
        for c in cmds:
            j["proc"] = subprocess.Popen(c, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT, env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
            if j["proc"].wait() != 0 or j["status"] == "cancelled":
                j.update(status="cancelled" if j["status"] == "cancelled" else "failed", finished=time.time())
                return
    for p in DATA.glob("space*.json"):
        STATE["blobs"][p.stem] = _blob(p)
    j.update(status="done", finished=time.time())


@app.post("/space/run")
def space_run(req: SpaceRun):
    w, s, e, n = req.bbox
    if not (w < e and s < n) or (e - w) * (n - s) > 0.06:
        raise HTTPException(422, "bbox must be W<E, S<N and at most ~0.06 deg² (about 600 km²) for a live run")
    name = re.sub(r"[^a-z0-9_]", "_", (req.name or f"run_{req.date[:10]}_{w:.2f}_{s:.2f}").lower())[:48]
    if any(j["status"] == "running" for j in JOBS.values()):
        raise HTTPException(429, "a Space-mode run is already in progress")
    jid = uuid.uuid4().hex[:10]
    JOBS[jid] = {"id": jid, "name": name, "status": "running", "started": time.time()}
    threading.Thread(target=_space_job, args=(jid, req), daemon=True).start()
    return _pub(JOBS[jid])


def _pub(j: dict) -> dict:
    return {k: v for k, v in j.items() if k != "proc"}


@app.get("/space/jobs")
def space_jobs():
    return [_pub(j) for j in JOBS.values()]


@app.post("/space/jobs/{jid}/cancel")
def space_cancel(jid: str):
    j = JOBS.get(jid)
    if not j:
        raise HTTPException(404, "unknown job")
    if j["status"] == "running":
        j["status"] = "cancelled"
        if j.get("proc"):
            j["proc"].kill()
    return _pub(j)


@app.get("/space/check")
def space_check(bbox: str, date: str):
    """Fast pre-check (catalogue search only): are there same-orbit Sentinel-1 before/after pairs for this area and date?"""
    from src.space import data as sdata
    try:
        b = tuple(float(v) for v in bbox.split(","))
        pairs = sdata.s1_pairs(b, pd.Timestamp(date))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"bad input or catalogue unavailable: {type(e).__name__}")
    return {"ok": bool(pairs), "pairs": [{k: p[k] for k in ("orbit", "state", "before_t", "after_t")} for p in pairs],
            "message": None if pairs else "No same-orbit Sentinel-1 pair within 12 days after the event: try a later date or a larger area."}


@app.get("/space/events")
def space_events(request: Request):
    return send(blob_or_404("space_index"), request)


SITREP_LOCAL = {"hi": "## हिन्दी", "ne": "## नेपाली"}


@app.get("/space/{name}/sitrep")
def space_sitrep(name: str, lang: str = "en", fmt: str = "md"):
    p = RESULTS / "space" / re.sub(r"[^a-z0-9_]", "", name) / "sitrep.md"
    if not p.exists():
        raise HTTPException(404, "no sitrep for this event")
    parts = re.split(r"\n(?=## )", p.read_text(encoding="utf-8"))
    local = lambda x: any(x.startswith(h) for h in SITREP_LOCAL.values())  # noqa: E731
    if lang in SITREP_LOCAL:
        parts = [parts[0].split("\n")[0], ""] + [x for x in parts if x.startswith(SITREP_LOCAL[lang])]
    else:
        parts = [x for x in parts if not local(x)]
    md = "\n".join(parts)
    if fmt != "html":
        return Response(md, media_type="text/markdown; charset=utf-8")
    import html as _h
    body = "".join(f"<h2>{_h.escape(x[3:])}</h2>" if x.startswith("## ") else f"<h1>{_h.escape(x[2:])}</h1>" if x.startswith("# ")
                   else f"<li>{_h.escape(x[2:])}</li>" if x.startswith("- ") else f"<p>{_h.escape(x)}</p>" if x else "" for x in md.split("\n")).replace("**", "")
    return Response(f"<!doctype html><meta charset=utf-8><title>PRAHAR sitrep {name}</title><style>body{{font:13px/1.45 system-ui;max-width:760px;margin:20px auto}}h1{{font-size:18px}}h2{{font-size:14px;border-bottom:1px solid #ccc}}</style>{body}",
                    media_type="text/html; charset=utf-8")


@app.get("/space/{name}/layers.zip")
def space_layers(name: str):
    import io
    import zipfile
    d = RESULTS / "space" / re.sub(r"[^a-z0-9_]", "", name)
    if not (d / "summary.json").exists():
        raise HTTPException(404, "unknown event")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(d.iterdir()):
            if f.suffix in (".geojson", ".tif", ".json", ".md", ".html", ".png") and f.name not in ("osm_before.json", "dem.tif"):
                z.write(f, f.name)
    return Response(buf.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{d.name}_prahar_layers.zip"'})


@app.get("/space/jobs/{jid}")
def space_job(jid: str):
    j = JOBS.get(jid)
    if not j:
        raise HTTPException(404, "unknown job")
    log = RESULTS / "space" / f"{j['name']}_run.log"
    txt = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    done = [label for key, label in STAGES if key in txt]
    return _pub(j) | {"elapsed_s": round((j.get("finished") or time.time()) - j["started"]), "stages": done, "log_tail": txt.splitlines()[-6:]}
