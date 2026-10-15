import type * as GeoJSON from 'geojson'
import { useMemo, useState } from 'react'
import FloodMap, { type Basemap } from '../components/FloodMap'
import PlaceSearch, { type Place } from '../components/PlaceSearch'
import ObjectCard, { type ObjProps } from '../components/ObjectCard'
import { BasemapSwitch, Bar } from '../components/ui'
import { pretty, useData, type Impact as ImpactData, type Snapshot, type Station } from '../lib/data'
import { useRiskPoints } from '../lib/points'

const CLS = [['CRITICAL', '#e0115f'], ['HIGH', '#ff4d2e'], ['MODERATE', '#ff9f1c'], ['LOW', '#f5d547']] as const

export default function Impact() {
  const im = useData<ImpactData>('impact')
  const stations = useData<Station[]>('stations')
  const snap = useData<Snapshot>('snapshot')
  const [base, setBase] = useState<Basemap>('satellite')
  const [is3d, set3d] = useState(false)
  const [b, setB] = useState<ObjProps | null>(null)
  const marks = useData<GeoJSON.FeatureCollection>('landmarks')
  const [focus, setFocus] = useState<{ lat: number; lon: number; zoom: number } | null>(null)
  const [tab, setTab] = useState<'buildings' | 'assets'>('buildings')
  const risk = useRiskPoints(stations, snap, false)
  const points = useMemo(() => [
    ...risk,
    ...(im?.bridges ?? []).map((x, i) => ({ id: `br${i}`, lat: x.lat, lon: x.lon, color: '#38bdf8', size: 12, label: `Bridge: ${x.name} (${x.dist_water_m} m from water)` })),
  ], [risk, im])
  const flyTo = (station: string) => {
    const s = im?.by_station.find(x => x.station === station)
    const st = stations?.find(x => x.station === station)
    const c = s?.lon != null ? s : st
    if (c?.lat != null && c.lon != null) setFocus({ lat: c.lat, lon: c.lon, zoom: 14.5 })
  }
  if (!im) return null
  const maxSt = Math.max(...im.by_station.map(s => s.exposed))

  return (
    <div className="grid h-full xl:grid-cols-[380px_1fr]">
      <div className="space-y-4 overflow-y-auto border-r border-line p-4">
        <div>
          <div className="label">04 · Exposure</div>
          <h1 className="mt-1 font-display text-5xl uppercase">Impact</h1>
          <p className="text-mute">What could be affected?</p>
        </div>

        <div className="glass rounded-xl p-4">
          <div className="label">Buildings potentially exposed</div>
          <div className="mt-2 font-display text-7xl leading-none text-severe">{im.buildings_exposed.toLocaleString()}</div>
          <div className="mt-1 text-xs text-mute">scored MODERATE or above, of {im.buildings_in_radius.toLocaleString()} ML-detected buildings within 5 km of any rain gauge (coloured by that gauge's hazard)</div>
          <div className="mt-4 flex h-2 overflow-hidden rounded-full">
            {CLS.map(([k, c]) => <div key={k} style={{ width: `${(im.by_class[k] / (im.buildings_exposed + im.by_class.LOW)) * 100}%`, background: c }} />)}
          </div>
          <div className="mt-2 grid grid-cols-4 gap-1 text-center">
            {CLS.map(([k, c]) => <div key={k}><div className="font-mono text-sm" style={{ color: c }}>{im.by_class[k].toLocaleString()}</div><div className="text-[9px] tracking-wider text-mute">{k}</div></div>)}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2">
          {[['Road segments', im.roads], ['Bridges', im.bridges.length], ['Schools / health', im.schools.length + im.health.length]].map(([k, v]) => (
            <div key={String(k)} className="glass rounded-xl p-3"><div className="font-mono text-2xl">{v}</div><div className="text-[11px] text-mute">{k}</div></div>
          ))}
        </div>

        <div className="glass rounded-xl p-4">
          <div className="mb-3 flex gap-1 font-mono text-[11px] uppercase">
            {(['buildings', 'assets'] as const).map(t => <button key={t} onClick={() => setTab(t)} className={`rounded-full px-3 py-1 ${tab === t ? 'bg-ink text-bg' : 'text-mute'}`}>{t === 'buildings' ? 'By station' : 'Bridges'}</button>)}
          </div>
          {tab === 'buildings' ? im.by_station.sort((a, c) => c.exposed - a.exposed).map(s => (
            <button key={s.station} className="mb-2.5 block w-full text-left hover:opacity-80" onClick={() => flyTo(s.station)}>
              <div className="flex justify-between text-sm"><span>{pretty(s.station)}</span><span className="font-mono">{s.exposed.toLocaleString()} <span className="text-mute">/ {s.buildings.toLocaleString()}</span></span></div>
              <div className="mt-1"><Bar value={s.exposed} max={maxSt} color="var(--color-severe)" /></div>
            </button>
          )) : (
            <ul className="max-h-60 space-y-1 overflow-y-auto text-sm">{im.bridges.map((x, i) => (
              <li key={i} className="flex justify-between"><span className="truncate">{x.name === 'unnamed' ? `Bridge (${x.type})` : x.name}</span><span className="font-mono text-xs text-mute">{x.dist_water_m} m</span></li>))}
            </ul>
          )}
        </div>

        <div className="rounded-xl border border-dashed border-line p-4 text-xs text-mute">
          <div className="label mb-1 text-alert!">Exposure proxy, not a damage estimate</div>
          {im.method}. Building polygons were extracted from satellite imagery by Microsoft's pretrained deep segmentation model;
          landmarks and place names come from OpenStreetMap. A hydraulic inundation extent and depth would replace this proxy next.
          <div className="mt-2">{im.sources.join(' · ')}</div>
        </div>
      </div>

      <div className="relative min-h-[600px]">
        <FloodMap basemap={base} terrain3d={is3d} points={points} tiledBuildings landmarks={marks} coverage={im?.coverage} focus={focus} onBuilding={p => setB(p as unknown as ObjProps)} />
        <PlaceSearch className="absolute left-4 top-4 z-10" places={[
          ...(stations ?? []).map(s => ({ name: s.station, lon: s.lon, lat: s.lat, kind: `station · ${s.district}` })),
          ...(marks?.features ?? []).filter(f => (f.properties as Record<string, unknown>)?.place).map(f => ({ name: String((f.properties as Record<string, unknown>).name), lon: (f.geometry as GeoJSON.Point).coordinates[0], lat: (f.geometry as GeoJSON.Point).coordinates[1], kind: `${String((f.properties as Record<string, unknown>).kind)} · ${(f.geometry as GeoJSON.Point).coordinates[1].toFixed(2)}°N ${(f.geometry as GeoJSON.Point).coordinates[0].toFixed(2)}°E` }))] as Place[]}
          onPick={p => setFocus({ lon: p.lon, lat: p.lat, zoom: 15 })} />
        <div className="absolute left-1/2 top-4 -translate-x-1/2"><BasemapSwitch value={base} onChange={setBase} is3d={is3d} on3d={set3d} /></div>
        <div className="glass absolute bottom-4 left-14 rounded-lg px-3 py-2 text-[11px] text-mute">Pick a station on the left to fly to its buildings · click a building · outlines: solid live gauge · dashed last gauge report · dotted district estimate</div>
        {b && <ObjectCard o={b} stations={im.station_p} onClose={() => setB(null)} />}
      </div>
    </div>
  )
}
