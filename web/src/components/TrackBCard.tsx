import { Link } from 'react-router-dom'
import { useData } from '../lib/data'
import type { SpaceData } from '../pages/Space'

// Headline Track B result, read from the exported Trishuli run (numbers are never typed by hand).
export default function TrackBCard({ compact = false }: { compact?: boolean }) {
  const d = useData<SpaceData>('space_trishuli')
  const e = d?.emsr_check
  if (!d || !e) return null
  const u = e.pixel.union, b = e.buildings.union, r = e.roads.union
  const items: [string, string][] = [
    [`${Math.round(b.recall * 100)}%`, `of EMS-damaged buildings found (${b.tp}/${b.ems_damaged})`],
    [`${Math.round(u.precision * 100)}%`, 'area precision against EMS'],
    [`${Math.round((b.osm_precision ?? 0) * 100)}%`, 'of flagged buildings next to EMS-confirmed damage'],
    [`${r.tp}/${r.ems_damaged}`, 'damaged roads found'],
    [`${d.cutoff.counts['CUT OFF'] ?? 0}`, 'settlements found cut off from the hospital'],
    [d.runtime_s ? `${Math.round(d.runtime_s / 60)} min` : '—', 'from raw satellite data to report'],
  ]
  return (
    <div className={`rounded-2xl border border-brand/40 bg-black/55 backdrop-blur ${compact ? 'p-4' : 'p-6 md:p-8'}`}>
      <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-brand">Track B · mapping flood damage from space</div>
      <h3 className={`mt-1 font-display ${compact ? 'text-xl' : 'text-3xl md:text-4xl'} text-ink`}>Checked against Copernicus EMS: Trishuli GLOF, Nepal, Aug 2026</h3>
      <p className="mt-1 text-sm text-ink/75">Run blind for any area and date from Sentinel-1, Sentinel-2, the Copernicus DEM and pre-event OpenStreetMap. EMSR927 rapid mapping was used only to check the answer.</p>
      <div className={`mt-4 grid gap-3 ${compact ? 'grid-cols-3 md:grid-cols-6' : 'grid-cols-2 md:grid-cols-3'}`}>
        {items.map(([v, l]) => (
          <div key={l} className="rounded-xl border border-line bg-black/30 p-3">
            <div className={`font-mono ${compact ? 'text-xl' : 'text-3xl'} text-brand`}>{v}</div>
            <div className="text-xs text-ink/70">{l}</div>
          </div>))}
      </div>
      <Link to="/app/space" className="mt-4 inline-block rounded-full bg-brand px-5 py-2 text-sm font-semibold text-bg hover:brightness-110">Open Space mode →</Link>
    </div>
  )
}
