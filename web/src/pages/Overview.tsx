import { useState } from 'react'
import type { Basemap } from '../components/FloodMap'
import { Link } from 'react-router-dom'
import { Area, AreaChart, ReferenceLine, ResponsiveContainer, XAxis, YAxis } from 'recharts'
import FloodMap from '../components/FloodMap'
import TrackBCard from '../components/TrackBCard'
import StationDrawer from '../components/StationDrawer'
import { BasemapSwitch, Bar, Panel, Stat, TierBadge } from '../components/ui'
import { pct, pretty, TIER_COLOR, useData, type Impact, type ModelData, type Snapshot, type Station, type TimelinePt } from '../lib/data'
import { useRiskPoints } from '../lib/points'

const STATUS_COLOR = { available: 'var(--color-normal)', missing: 'var(--color-severe)', pending: 'var(--color-mute)' }

export default function Overview() {
  const stations = useData<Station[]>('stations')
  const snap = useData<Snapshot>('snapshot')
  const tl = useData<TimelinePt[]>('timeline')
  const model = useData<ModelData>('model')
  const im = useData<Impact>('impact')
  const watch = useData<{ day: string; recall_at_3: Record<string, number>; ranking: { district: string; score: number; rank: number }[] }>('district_watch')
  const points = useRiskPoints(stations, snap)
  const [sel, setSel] = useState<string | null>(null)
  const [base, setBase] = useState<Basemap>('dark')
  const [is3d, set3d] = useState(false)
  if (!snap) return null

  const top = snap.stations[0]
  const severe = snap.tier_counts.SEVERE + snap.tier_counts.EXTREME
  const selSnap = snap.stations.find(s => s.station === sel)
  const maxGroup = model?.importance_groups[0]?.importance ?? 1

  return (
    <div className="grid gap-4 p-4 xl:grid-cols-[360px_1fr]">
      <div className="xl:col-span-2"><TrackBCard compact /></div>
      <div className="space-y-4">
        <Panel>
          <div className="label">Current regional risk · peak station</div>
          <div className="mt-4 font-display text-7xl uppercase leading-none" style={{ color: TIER_COLOR[top.tier] }}>{top.tier}</div>
          <div className="mt-2 flex items-baseline gap-3">
            {top.trigger === 'rainfall' ? (<>
              <span className="whitespace-nowrap font-mono text-4xl font-semibold">{(top.signals.rain_24h ?? 0).toFixed(0)} mm</span>
              <span className="font-mono text-xs text-mute">rain in 24 h<br />IMD threshold</span>
            </>) : (<>
              <span className="font-mono text-4xl font-semibold">{pct(top.p)}</span>
              <span className="font-mono text-sm text-mute">calibrated flood probability</span>
            </>)}
          </div>
          <div className="mt-1 font-mono text-[11px] text-mute">ML {pct(top.p)} · rain 24 h {(top.signals.rain_24h ?? 0).toFixed(0)} mm · set by {top.trigger === 'rainfall' ? 'rainfall threshold' : 'ML model'}</div>
          <button onClick={() => setSel(top.station)} className="mt-2 text-sm text-water hover:underline">{pretty(top.station)}, {top.district} →</button>
        </Panel>

        <div className="grid grid-cols-2 gap-4">
          <Stat label="≥ Severe" value={severe} sub="stations" color="var(--color-severe)" />
          <Stat label="Reporting" value={`${snap.stations_reporting}/${snap.stations_total}`} sub="rain gauges, 24 h" />
          <Stat label="Confidence" value={pct(top.confidence)} sub={`conformal · 90% set: ${top.cp_set_90.replace('_', ' ').toLowerCase()}`} />
          <Stat label="Buildings" value={im ? im.buildings_exposed.toLocaleString() : '—'} sub="moderate+ exposure" color="var(--color-alert)" />
        </div>

        {tl && (
          <Panel title="Regional risk trajectory" right={<Link to="../forecast" className="text-xs text-water">Forecast →</Link>}>
            <div className="h-28">
              <ResponsiveContainer>
                <AreaChart data={tl} margin={{ top: 4, right: 0, left: -28, bottom: 0 }}>
                  <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#ff4d2e" stopOpacity={0.5} /><stop offset="1" stopColor="#ff4d2e" stopOpacity={0} /></linearGradient></defs>
                  <XAxis dataKey="t" hide /><YAxis domain={[0, 1]} tick={{ fontSize: 10, fill: '#a9c2b3' }} tickFormatter={v => `${v * 100}`} />
                  <ReferenceLine x={snap.replay_time.slice(0, 16)} stroke="#f1f8f3" strokeDasharray="3 3" />
                  <Area dataKey="max_p" stroke="#ff4d2e" fill="url(#g)" strokeWidth={2} type="monotone" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-1 font-mono text-[10px] text-mute">max station probability · −72 h → +24 h · dashed = replay time</div>
          </Panel>
        )}

        {model && (
          <Panel title="What drives the model (global)">
            <div className="space-y-2.5">
              {model.importance_groups.slice(0, 5).map(g => (
                <div key={g.group}>
                  <div className="flex justify-between text-xs"><span>{g.group}</span><span className="font-mono text-mute">{(g.importance * 100).toFixed(0)}%</span></div>
                  <div className="mt-1"><Bar value={g.importance} max={maxGroup} /></div>
                </div>
              ))}
            </div>
            <p className="mt-3 text-[11px] text-mute">XGBoost gain importance grouped by modality. Importance, not causation.</p>
          </Panel>
        )}

        {watch && (
          <Panel title={`Districts to watch · ${watch.day}`}>
            <ol className="space-y-1.5 text-sm">
              {watch.ranking.slice(0, 3).map(r => (
                <li key={r.district} className="flex justify-between"><span><span className="font-mono text-mute">{r.rank}.</span> {r.district}</span><span className="font-mono text-xs text-mute">{r.score.toFixed(2)}</span></li>
              ))}
            </ol>
            <p className="mt-3 text-[11px] text-mute">A daily ranking from the district-day model (gauges + USDMA stations + ERA5), not a warning. The flooded district was in the top 3 for {pct(watch.recall_at_3.external_model)} of documented events after Aug 2023 (district history alone: {pct(watch.recall_at_3.external_prior)}; chance {pct(watch.recall_at_3.chance)}).</p>
          </Panel>
        )}

        <Panel title="Data sources">
          <ul className="space-y-2 text-sm">
            {snap.sources.map(s => (
              <li key={s.name} className="flex items-start gap-2">
                <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ background: STATUS_COLOR[s.status] }} />
                <div><div>{s.name} <span className="font-mono text-[10px] uppercase text-mute">{s.status}</span></div><div className="text-xs text-mute">{s.detail}</div></div>
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <div className="relative min-h-[560px] overflow-hidden rounded-xl border border-line xl:sticky xl:top-4 xl:h-[calc(100vh-5.5rem)]">
        <FloodMap basemap={base} terrain3d={is3d} points={points} selected={sel} onSelect={setSel} />
        <div className="glass absolute left-4 top-4 rounded-xl p-3">
          <div className="label mb-2">Stations by tier</div>
          <div className="flex flex-col gap-1.5">{(['EXTREME', 'SEVERE', 'ALERT', 'WATCH', 'NORMAL'] as const).map(t => (
            <div key={t} className="flex items-center justify-between gap-6"><TierBadge tier={t} /><span className="font-mono text-sm">{snap.tier_counts[t]}</span></div>
          ))}</div>
        </div>
      <div className="absolute left-1/2 top-4 -translate-x-1/2"><BasemapSwitch value={base} onChange={setBase} is3d={is3d} on3d={set3d} /></div>
        {selSnap && <StationDrawer s={selSnap} onClose={() => setSel(null)} />}
      </div>
    </div>
  )
}
