import * as maplibregl from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import { useEffect, useRef, useState } from 'react'
import { PageHead, Panel, Stat } from '../components/ui'
import { useData } from '../lib/data'

type FC = GeoJSON.FeatureCollection
type Score = { precision: number; recall: number; f1: number; iou: number }
type Settlement = { name: string | null; place: string; lon: number; lat: number; before_km: number | null; after_km: number | null; status: string }
export type SpaceData = {
  name: string; event_utc: string; bbox: [number, number, number, number]; detector: string; osm_snapshot: string
  s1_pairs: { orbit: number; state: string; before_t: string; after_t: string }[]
  flood: Record<string, number>; damage: Record<'buildings' | 'roads' | 'bridges', { total: number; hit: number }>
  cutoff: { destination: string; counts: Record<string, number>; settlements: Settlement[] }
  model: { arch?: string; flood_threshold?: number; test_scores_unseen_events?: { flood_tuned?: Score; any_water?: Score; flood_argmax?: Score } }
  layers: { flood: FC; buildings_hit: FC; roads: FC; bridges: FC }
  sitrep: string
  s2?: { used: boolean; pre?: string; post?: string; both_clear?: number; reason?: string } | null
  runtime_s?: number | null
  rescue?: { rule: string; settlements: { name: string; place: string | null; lon: number; lat: number; by: string[]; buildings: number; landing_sites: { lon: number; lat: number; dist_km: number; flat_m2: number }[] }[] } | null
  emsr_check?: { ems: string[]; aois: string[]; aoi_km2: number; ems_event_km2: number
    pixel: Record<'ai_water' | 'debris' | 'union', Score & { km2_in_aoi: number }>
    buildings: Record<'ai_water' | 'debris' | 'union', { ems_damaged: number; tp: number; recall: number; osm_flagged_in_aoi?: number; osm_precision?: number | null }>
    roads: Record<'ai_water' | 'debris' | 'union', { ems_damaged: number; tp: number; recall: number }> } | null
  debris_conf?: FC | null
  flowdir?: { west: number; north: number; step: number; w: number; h: number; dr: number[]; dc: number[]; dir_b64: string } | null
  debris?: { summary: { km2: number; damage: Record<'buildings' | 'roads' | 'bridges', { total: number; hit: number }>; cutoff: Record<string, number> }; cutoff: { settlements: Settlement[] }; polygons: FC; buildings_hit: FC; roads: FC } | null
}

maplibregl.setWorkerUrl(workerUrl)   // as in FloodMap: the page can be opened directly

const SAT = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
const STATUS_COLOR: Record<string, string> = { 'CUT OFF': '#e0115f', 'longer route': '#ff9f1c', connected: '#3ddc97', 'not connected before': '#8fa79a' }

// Flood-path tracer: follow the D8 flow directions (Priority-Flood filled Copernicus DEM, exported per event) from a
// clicked upstream point to the edge of the area, then list what lies within the 200 m river corridor of that path.
type Trace = { from: [number, number]; km: number; hits: { kind: 'settlement' | 'bridge'; name: string; km: number; status?: string }[] }
const CORRIDOR_M = 200
const metres = (a: number[], b: number[]) => {
  const k = Math.PI / 180, x = (b[0] - a[0]) * k * Math.cos(((a[1] + b[1]) / 2) * k), y = (b[1] - a[1]) * k
  return 6371000 * Math.hypot(x, y)
}
function tracePath(fd: NonNullable<SpaceData['flowdir']>, dir: Uint8Array, lon: number, lat: number): number[][] {
  let c = Math.floor((lon - fd.west) / fd.step), r = Math.floor((fd.north - lat) / fd.step)
  const pts: number[][] = []
  for (let i = 0; i < fd.w * fd.h && r >= 0 && r < fd.h && c >= 0 && c < fd.w; i++) {
    pts.push([fd.west + (c + 0.5) * fd.step, fd.north - (r + 0.5) * fd.step])
    const k = dir[r * fd.w + c]
    if (k === 255) break
    r += fd.dr[k]; c += fd.dc[k]
  }
  return pts
}
function alongPath(d: SpaceData, pts: number[][]): Trace['hits'] {
  const cum = [0]
  for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + metres(pts[i - 1], pts[i]))
  const near = (q: number[]) => { let best = Infinity, at = 0; pts.forEach((p, i) => { const m = metres(p, q); if (m < best) { best = m; at = i } }); return { m: best, km: cum[at] / 1000 } }
  const hits: Trace['hits'] = []
  d.cutoff.settlements.forEach(st => { const n = near([st.lon, st.lat]); if (n.m <= CORRIDOR_M) hits.push({ kind: 'settlement', name: st.name ?? 'unnamed', km: n.km, status: st.status }) })
  d.layers.bridges.features.forEach(b => {
    const g = b.geometry as GeoJSON.LineString
    const mid = g.coordinates[Math.floor(g.coordinates.length / 2)]
    const n = near(mid); if (n.m <= CORRIDOR_M) hits.push({ kind: 'bridge', name: String((b.properties as Record<string, unknown>)?.name ?? 'bridge'), km: n.km })
  })
  return hits.sort((a, b) => a.km - b.km)
}

function SpaceMap({ d, tracing, onTrace }: { d: SpaceData; tracing: boolean; onTrace: (t: Trace | null) => void }) {
  const el = useRef<HTMLDivElement>(null)
  const map = useRef<maplibregl.Map | null>(null)
  const dirRef = useRef<Uint8Array | null>(null)
  const tracingRef = useRef(tracing)
  tracingRef.current = tracing
  useEffect(() => {
    if (d.flowdir) dirRef.current = Uint8Array.from(atob(d.flowdir.dir_b64), ch => ch.charCodeAt(0))
    if (map.current) map.current.getCanvas().style.cursor = tracing ? 'crosshair' : ''
  }, [d, tracing])
  useEffect(() => {
    if (!el.current) return
    const [w, s, e, n] = d.bbox
    const m = new maplibregl.Map({
      container: el.current, bounds: [[w, s], [e, n]], fitBoundsOptions: { padding: 20 }, attributionControl: { compact: true },
      style: { version: 8, sources: { sat: { type: 'raster', tiles: [SAT], tileSize: 256, attribution: 'Imagery © Esri · Contains modified Copernicus Sentinel data · © OpenStreetMap contributors' } },
               layers: [{ id: 'sat', type: 'raster', source: 'sat', paint: { 'raster-brightness-max': 0.75 } }] },
    })
    map.current = m
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    m.on('click', (ev: maplibregl.MapMouseEvent) => {
      if (!tracingRef.current || !d.flowdir || !dirRef.current) return
      const pts = tracePath(d.flowdir, dirRef.current, ev.lngLat.lng, ev.lngLat.lat)
      const src = m.getSource('trace') as maplibregl.GeoJSONSource | undefined
      src?.setData({ type: 'FeatureCollection', features: [{ type: 'Feature', geometry: { type: 'LineString', coordinates: pts }, properties: {} }] })
      let km = 0
      for (let i = 1; i < pts.length; i++) km += metres(pts[i - 1], pts[i]) / 1000
      onTrace({ from: [ev.lngLat.lng, ev.lngLat.lat], km, hits: alongPath(d, pts) })
    })
    m.on('load', () => {
      if (d.debris) {   // low-confidence rule layer, drawn under the AI floodwater
        m.addSource('deb', { type: 'geojson', data: d.debris.polygons })
        m.addLayer({ id: 'deb', type: 'fill', source: 'deb', paint: { 'fill-color': '#b5651d', 'fill-opacity': 0.45 } })
        m.addSource('deb-bld', { type: 'geojson', data: d.debris.buildings_hit })
        m.addLayer({ id: 'deb-bld', type: 'line', source: 'deb-bld', paint: { 'line-color': '#ffb347', 'line-width': 1.5 } })
        m.addSource('deb-roads', { type: 'geojson', data: d.debris.roads })
        m.addLayer({ id: 'deb-roads', type: 'line', source: 'deb-roads', paint: { 'line-color': '#ffb347', 'line-width': 2.5, 'line-dasharray': [2, 1.5] } })
      }
      if (d.debris_conf) {
        m.addSource('deb-conf', { type: 'geojson', data: d.debris_conf })
        m.addLayer({ id: 'deb-conf', type: 'line', source: 'deb-conf', paint: { 'line-color': '#ffe08a', 'line-width': 1.2 } })
      }
      m.addSource('flood', { type: 'geojson', data: d.layers.flood })
      m.addLayer({ id: 'flood', type: 'fill', source: 'flood', paint: { 'fill-color': ['match', ['get', 'class'], 'flood', '#1e90ff', '#0b3d91'], 'fill-opacity': 0.6 } })
      m.addSource('roads', { type: 'geojson', data: d.layers.roads })
      m.addLayer({ id: 'roads', type: 'line', source: 'roads', paint: { 'line-color': ['case', ['get', 'hit'], '#ff9f1c', '#ffffff'], 'line-width': ['case', ['get', 'hit'], 3, 1], 'line-opacity': ['case', ['get', 'hit'], 1, 0.45] } })
      m.addSource('bridges', { type: 'geojson', data: d.layers.bridges })
      m.addLayer({ id: 'bridges', type: 'line', source: 'bridges', paint: { 'line-color': ['case', ['get', 'hit'], '#e0115f', '#f5d547'], 'line-width': 4 } })
      m.addSource('bld', { type: 'geojson', data: d.layers.buildings_hit })
      m.addLayer({ id: 'bld', type: 'fill', source: 'bld', paint: { 'fill-color': '#ff2d2d', 'fill-opacity': 0.9 } })
      m.addLayer({ id: 'bld-line', type: 'line', source: 'bld', paint: { 'line-color': '#ffffff', 'line-width': 1 } })
      const pts: FC = { type: 'FeatureCollection', features: d.cutoff.settlements.map(r => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [r.lon, r.lat] }, properties: { ...r } })) }
      m.addSource('pl', { type: 'geojson', data: pts })
      m.addLayer({ id: 'pl', type: 'circle', source: 'pl', paint: { 'circle-radius': 7, 'circle-color': ['match', ['get', 'status'], 'CUT OFF', STATUS_COLOR['CUT OFF'], 'longer route', STATUS_COLOR['longer route'], 'connected', STATUS_COLOR.connected, STATUS_COLOR['not connected before']], 'circle-stroke-color': '#000', 'circle-stroke-width': 1.5 } })
      m.addLayer({ id: 'pl-txt', type: 'symbol', source: 'pl', layout: { 'text-field': ['get', 'name'], 'text-size': 12, 'text-offset': [0, 1.2], 'text-anchor': 'top', 'text-font': ['Open Sans Semibold'] }, paint: { 'text-color': '#fff', 'text-halo-color': '#000', 'text-halo-width': 1.5 } })
      m.addSource('trace', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
      m.addLayer({ id: 'trace-glow', type: 'line', source: 'trace', paint: { 'line-color': '#00e5ff', 'line-width': 9, 'line-opacity': 0.25 } })
      m.addLayer({ id: 'trace', type: 'line', source: 'trace', paint: { 'line-color': '#00e5ff', 'line-width': 3 } })
      const lz: FC = { type: 'FeatureCollection', features: (d.rescue?.settlements ?? []).flatMap(r => r.landing_sites.slice(0, 1).map(x => ({ type: 'Feature' as const, geometry: { type: 'Point' as const, coordinates: [x.lon, x.lat] }, properties: { for: r.name, km: x.dist_km } }))) }
      m.addSource('lz', { type: 'geojson', data: lz })
      m.addLayer({ id: 'lz', type: 'circle', source: 'lz', paint: { 'circle-radius': 9, 'circle-color': '#ffffff', 'circle-stroke-color': '#1e90ff', 'circle-stroke-width': 3 } })
      m.addLayer({ id: 'lz-txt', type: 'symbol', source: 'lz', layout: { 'text-field': 'H', 'text-size': 12, 'text-font': ['Open Sans Semibold'], 'text-allow-overlap': true }, paint: { 'text-color': '#1e90ff' } })
      m.on('click', 'lz', (ev: maplibregl.MapLayerMouseEvent) => {
        const p = ev.features?.[0]?.properties as Record<string, unknown> | undefined
        if (p) new maplibregl.Popup().setLngLat(ev.lngLat).setText(`Landing candidate for ${p.for} (${p.km} km): flat, dry, open 30 x 30 m patch (ICAO Annex 14 slope limits). Crew must check obstacles.`).addTo(m)
      })
      m.on('click', 'pl', (ev: maplibregl.MapLayerMouseEvent) => {
        const p = ev.features?.[0]?.properties as Record<string, unknown> | undefined
        if (p) new maplibregl.Popup().setLngLat(ev.lngLat).setText(`${p.name ?? 'Settlement'}: ${p.status} (road to ${d.cutoff.destination}: ${p.before_km ?? '—'} km before, ${p.after_km ?? 'no route'} after)`).addTo(m)
      })
    })
    return () => { m.remove(); map.current = null }
  }, [d, onTrace])
  return <div ref={el} className="h-[520px] w-full overflow-hidden rounded-xl" />
}

const f = (v?: number, d = 2) => (v == null ? '—' : v.toFixed(d))

type IndexEntry = { name: string; event_utc: string; bbox: number[]; checked: boolean }
type Job = { id: string; name: string; status: string; elapsed_s?: number; stages?: string[]; log_tail?: string[] }
const API = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '')
const title = (n: string) => n.replace(/_/g, ' ').replace(/^./, c => c.toUpperCase())

function RunArea({ onDone }: { onDone: (name: string) => void }) {
  const [bbox, setBbox] = useState('85.30,28.14,85.40,28.29')
  const [date, setDate] = useState('2026-08-25 22:00')
  const [job, setJob] = useState<Job | null>(null)
  const [err, setErr] = useState('')
  useEffect(() => {
    if (!job || job.status !== 'running') return
    const t = setInterval(async () => {
      const j: Job = await fetch(`${API}/space/jobs/${job.id}`).then(r => r.json())
      setJob(j)
      if (j.status === 'done') onDone(j.name)
    }, 4000)
    return () => clearInterval(t)
  }, [job, onDone])
  const start = async () => {
    setErr('')
    const r = await fetch(`${API}/space/run`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bbox: bbox.split(',').map(Number), date }) })
    const j = await r.json()
    if (!r.ok) setErr(typeof j.detail === 'string' ? j.detail : 'request rejected'); else setJob(j)
  }
  if (!API) return (
    <p className="text-sm text-ink/80">Live runs need the API (this is the static build). Locally:{' '}
      <code className="font-mono text-xs">python -m src.space.run --name myarea --bbox W,S,E,N --date "YYYY-MM-DD HH:MM"</code>, then{' '}
      <code className="font-mono text-xs">python -m src.space.report --name myarea</code> and <code className="font-mono text-xs">python scripts/export_space.py --name myarea</code>. About 5 to 15 minutes from raw satellite data; repeat runs reuse cached radar scenes.</p>
  )
  return (
    <div className="flex flex-wrap items-end gap-3 text-sm">
      <label className="flex flex-col gap-1"><span className="font-mono text-xs text-mute">Area W,S,E,N (WGS84)</span>
        <input value={bbox} onChange={e => setBbox(e.target.value)} className="w-64 rounded-md border border-line bg-transparent px-2 py-1 font-mono" /></label>
      <label className="flex flex-col gap-1"><span className="font-mono text-xs text-mute">Flood date and time (UTC)</span>
        <input value={date} onChange={e => setDate(e.target.value)} className="w-44 rounded-md border border-line bg-transparent px-2 py-1 font-mono" /></label>
      <button onClick={start} disabled={job?.status === 'running'} className="rounded-md bg-brand px-4 py-1.5 font-semibold text-black disabled:opacity-50">
        {job?.status === 'running' ? `Running... ${job.elapsed_s ?? 0} s` : 'Map this flood'}</button>
      {err && <span className="text-[#ff4d2e]">{err}</span>}
      {job && <div className="w-full font-mono text-xs text-mute">{job.status} · {(job.stages ?? []).join(' → ') || 'searching Sentinel-1...'}{job.status === 'failed' ? ` · ${(job.log_tail ?? []).slice(-1)[0] ?? ''}` : ''}</div>}
    </div>
  )
}

const LAYER_NAME = { ai_water: 'Floodwater (AI + Sentinel-2)', debris: 'Debris (radar + Sentinel-2)', union: 'Both layers' } as const

export default function Space() {
  const idx = useData<IndexEntry[]>('space_index')
  const [sel, setSel] = useState<string | null>(null)
  const [extra, setExtra] = useState<string[]>([])
  const name = sel ?? idx?.[0]?.name ?? 'dharali'
  const d = useData<SpaceData>(`space_${name}`)
  const names = [...new Set([...(idx ?? []).map(e => e.name), ...extra])]
  const onDone = (n: string) => { setExtra(x => [...x, n]); setSel(n) }
  const [tracing, setTracing] = useState(false)
  const [trace, setTrace] = useState<Trace | null>(null)
  if (!d) return null
  const t = d.model.test_scores_unseen_events
  const cut = d.cutoff.settlements.filter(s => s.status === 'CUT OFF')
  const flooded = (d.flood.ai_flood_km2_corridor ?? d.flood.water_km2) + (d.flood.s2_added_km2 ?? 0)
  return (
    <div className="mx-auto max-w-6xl p-6">
      <PageHead kicker="Space mode · Track B" title={`${title(d.name)} flood from space`}
        question="Where did the flood hit, what was damaged, and who is cut off? From Sentinel-1 radar, Sentinel-2 when clear, the Copernicus DEM and pre-event OpenStreetMap only." />
      <div className="mb-4 flex flex-wrap gap-2">{names.map(n => (
        <button key={n} onClick={() => setSel(n)} className={`rounded-full border px-3 py-1 text-sm ${n === name ? 'border-brand bg-brand/15 text-brand' : 'border-line text-ink/70'}`}>{title(n)}</button>))}
      </div>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        <Stat label="Flooded (200 m river corridor)" value={`${f(flooded, 1)} km²`} sub={d.detector} color="#4fb3f0" />
        <Stat label="Buildings hit" value={`${d.damage.buildings.hit}/${d.damage.buildings.total}`} sub={`OSM as of ${d.osm_snapshot}`} color="#ff2d2d" />
        <Stat label="Road segments hit" value={`${d.damage.roads.hit}/${d.damage.roads.total}`} sub={`bridges ${d.damage.bridges.hit}/${d.damage.bridges.total}`} color="#ff9f1c" />
        <Stat label="Settlements cut off" value={cut.length} sub={`no road to ${d.cutoff.destination}`} color="#e0115f" />
        <Stat label="AI flood F1 (unseen events)" value={f(t?.flood_tuned?.f1)} sub={`precision ${f(t?.flood_tuned?.precision)} · recall ${f(t?.flood_tuned?.recall)}`} color="var(--color-brand)" />
      </div>

      {d.debris && <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Debris (radar + Sentinel-2)" value={`${f(d.debris.summary.km2, 1)} km²`} sub={d.emsr_check ? `checked vs Copernicus EMS: precision ${f(d.emsr_check.pixel.debris.precision)}` : 'radar change; optical where clear; not validated here'} color="#b5651d" />
        <Stat label="Buildings on possible debris" value={`${d.debris.summary.damage.buildings.hit}/${d.debris.summary.damage.buildings.total}`} sub="outlined amber on the map" color="#ffb347" />
        <Stat label="Roads on possible debris" value={`${d.debris.summary.damage.roads.hit}/${d.debris.summary.damage.roads.total}`} sub={`bridges ${d.debris.summary.damage.bridges.hit}`} color="#ffb347" />
        <Stat label="Cut off if debris blocks roads" value={d.debris.summary.cutoff['CUT OFF'] ?? 0} sub={d.debris.cutoff.settlements.filter(s => s.status === 'CUT OFF' && s.name).map(s => s.name).join(', ') || '—'} color="#e0115f" />
      </div>}

      <Panel title={`Map · event ${d.event_utc.slice(0, 16)} UTC · blue = floodwater (AI + Sentinel-2), brown = debris (radar + Sentinel-2), amber = objects on debris, red/orange = objects in floodwater, dots = settlements`} className="mt-4">
        {d.flowdir && <div className="mb-2 flex flex-wrap items-center gap-3 text-sm">
          <button onClick={() => setTracing(t => !t)} className={`rounded-md border px-3 py-1 ${tracing ? 'border-[#00e5ff] bg-[#00e5ff]/15 text-[#00e5ff]' : 'border-line text-ink/80'}`}>
            {tracing ? 'Tracing: click any upstream point' : 'Trace a flood path'}</button>
          <span className="text-xs text-mute">Follows the terrain downhill (Copernicus DEM, D8 on a Priority-Flood filled surface) and lists settlements and bridges within the 200 m river corridor of the path.</span>
        </div>}
        <SpaceMap d={d} tracing={tracing} onTrace={setTrace} />
        {trace && <div className="mt-2 rounded-lg border border-[#00e5ff]/40 p-3 text-sm">
          <div className="font-mono text-xs text-mute">Flood path from {trace.from[1].toFixed(4)}, {trace.from[0].toFixed(4)} · {trace.km.toFixed(1)} km to the edge of the area</div>
          {trace.hits.length === 0 ? <div className="mt-1">No mapped settlement or bridge within 200 m of this path.</div> :
            <ol className="mt-1 grid gap-x-6 sm:grid-cols-2">{trace.hits.map((h, i) => (
              <li key={i}><span className="font-mono text-[#00e5ff]">{h.km.toFixed(1)} km</span> · {h.kind === 'bridge' ? 'Bridge' : h.name}{h.kind === 'bridge' && h.name !== 'bridge' ? ` (${h.name})` : ''}{h.status ? <span style={{ color: STATUS_COLOR[h.status] }}> · {h.status}</span> : ''}</li>))}</ol>}
        </div>}
        <p className="mt-2 text-[11px] text-mute">Radar pairs (same orbit): {d.s1_pairs.map(p => `track ${p.orbit} ${p.state} ${p.before_t.slice(0, 10)} → ${p.after_t.slice(0, 16)}`).join(' · ')}.
          {' '}Sentinel-2: {d.s2 ? (d.s2.used ? `used where clear (${Math.round((d.s2.both_clear ?? 0) * 100)} % of the area clear before and after)` : d.s2.reason) : 'not run'}.
          {' '}Yellow outline = debris seen by radar and optical. H = helicopter landing candidate. Click a settlement for its route.{d.runtime_s ? ` Answered in ${Math.floor(d.runtime_s / 60)} min ${Math.round(d.runtime_s % 60)} s from raw data.` : ''}</p>
      </Panel>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        <Panel title="Who is cut off? (road graph before vs after, flooded roads and bridges removed)">
          <div className="max-h-80 overflow-y-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left font-mono text-xs text-mute"><th className="py-1 font-normal">Settlement</th><th className="font-normal">Status</th><th className="font-normal">Route before</th><th className="font-normal">After</th></tr></thead>
              <tbody>{[...d.cutoff.settlements].sort((a, b) => (a.status === 'CUT OFF' ? -1 : 1) - (b.status === 'CUT OFF' ? -1 : 1)).map((s, i) => (
                <tr key={i} className="border-t border-line"><td className="py-1">{s.name ?? '—'} <span className="text-mute">{s.place}</span></td>
                  <td style={{ color: STATUS_COLOR[s.status] }}>{s.status}</td><td className="font-mono">{s.before_km ?? '—'} km</td><td className="font-mono">{s.after_km == null ? 'no route' : `${s.after_km} km`}</td></tr>))}</tbody>
            </table>
          </div>
        </Panel>
        <Panel title="AI model · U-Net trained on Kuro Siwo, tested on unseen flood events">
          <table className="w-full font-mono text-sm">
            <thead><tr className="text-left text-xs text-mute"><th className="py-1 font-normal">Class</th><th className="font-normal">Precision</th><th className="font-normal">Recall</th><th className="font-normal">F1</th><th className="font-normal">IoU</th></tr></thead>
            <tbody>{([['Flood (tuned threshold)', t?.flood_tuned], ['Flood (arg-max)', t?.flood_argmax], ['Any water', t?.any_water]] as [string, Score | undefined][]).map(([k, v]) => (
              <tr key={k} className="border-t border-line"><td className="py-1 font-sans">{k}</td><td>{f(v?.precision)}</td><td>{f(v?.recall)}</td><td className="text-brand">{f(v?.f1)}</td><td>{f(v?.iou)}</td></tr>))}</tbody>
          </table>
          <p className="mt-2 text-[11px] text-mute">Flood threshold {f(d.model.flood_threshold)} chosen on the validation split, never on test. Kuro Siwo test events are mostly lowland floods; no labelled Himalayan scenes exist to score on.</p>
        </Panel>
      </div>

      {d.emsr_check && <Panel title={`Checked against Copernicus EMS rapid mapping (check only, never an input) · EMS mapped: ${d.emsr_check.ems.join(', ')} · ${d.emsr_check.aois.join(' + ')}`} className="mt-4">
        <div className="grid gap-4 lg:grid-cols-[1fr_1.1fr]">
          <div>
            <table className="w-full font-mono text-sm">
              <thead><tr className="text-left text-xs text-mute"><th className="py-1 font-normal">PRAHAR layer</th><th className="font-normal">Area P</th><th className="font-normal">Area R</th><th className="font-normal">IoU</th><th className="font-normal">EMS damaged bldgs found</th><th className="font-normal">Roads found</th></tr></thead>
              <tbody>{(['ai_water', 'debris', 'union'] as const).map(k => (
                <tr key={k} className="border-t border-line"><td className="py-1 font-sans">{LAYER_NAME[k]}</td>
                  <td>{f(d.emsr_check!.pixel[k].precision)}</td><td>{f(d.emsr_check!.pixel[k].recall)}</td><td className="text-brand">{f(d.emsr_check!.pixel[k].iou)}</td>
                  <td>{d.emsr_check!.buildings[k].tp}/{d.emsr_check!.buildings[k].ems_damaged}</td><td>{d.emsr_check!.roads[k].tp}/{d.emsr_check!.roads[k].ems_damaged}</td></tr>))}</tbody>
            </table>
            <p className="mt-2 text-[11px] text-mute">Scored only inside the EMS areas of interest ({f(d.emsr_check.aoi_km2, 1)} km², EMS event area {f(d.emsr_check.ems_event_km2, 2)} km²). EMS mapped from very-high-resolution optical images; we use free 10 m Sentinel data. Buildings: EMS-graded damaged buildings lying on our detected pixels (one-pixel tolerance).</p>
          </div>
          <img src={`/img/space/${d.name}_emsr.png`} alt="Error map: green agree, red PRAHAR only, blue EMS only" className="w-full rounded-lg border border-line" />
        </div>
      </Panel>}

      {d.rescue && d.rescue.settlements.length > 0 && <Panel title="Rescue priorities · cut-off settlements, largest first, with the nearest helicopter landing candidate" className="mt-4">
        <table className="w-full text-sm">
          <thead><tr className="text-left font-mono text-xs text-mute"><th className="py-1 font-normal">Settlement</th><th className="font-normal">≈ Buildings</th><th className="font-normal">Cut off by</th><th className="font-normal">Landing candidate (lat, lon)</th><th className="font-normal">Distance</th></tr></thead>
          <tbody>{d.rescue.settlements.map(r => (
            <tr key={r.name} className="border-t border-line"><td className="py-1">{r.name} <span className="text-mute">{r.place}</span></td><td className="font-mono">{r.buildings}</td><td>{r.by.join(' + ')}</td>
              <td className="font-mono">{r.landing_sites[0] ? `${r.landing_sites[0].lat}, ${r.landing_sites[0].lon}` : 'none found'}</td><td className="font-mono">{r.landing_sites[0] ? `${r.landing_sites[0].dist_km} km` : '—'}</td></tr>))}</tbody>
        </table>
        <p className="mt-2 text-[11px] text-mute">{d.rescue.rule}. Not flooded, no debris, off the mapped river channel, no pre-event building. Map candidates only; wires, trees and approach paths must be checked by the crew.</p>
      </Panel>}

      <Panel title="Map any flood · area + date → flood, damage and cut-off from raw satellite data" className="mt-4">
        <RunArea onDone={onDone} />
      </Panel>

      <Panel title="Situation report (generated by the system; every number comes from the maps)" className="mt-4">
        <pre className="max-h-96 overflow-y-auto whitespace-pre-wrap font-sans text-sm leading-relaxed text-ink/85">{d.sitrep.replace(/\*\*/g, '')}</pre>
      </Panel>
    </div>
  )
}
