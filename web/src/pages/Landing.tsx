import { Link } from 'react-router-dom'
import TrackBCard from '../components/TrackBCard'
import { fmtTime, pct, pretty, TIER_COLOR, useData, type ModelData, type Snapshot } from '../lib/data'

const CHAIN = [
  ['01', 'Will it flood?', 'Multimodal probability from rainfall, river, terrain and flood history.'],
  ['02', 'When?', 'Risk trajectory over the coming hours, peak and lead time.'],
  ['03', 'Where?', 'Station- and zone-level hotspots on a terrain map.'],
  ['04', 'How sure?', 'Uncertainty, source health and what happens when a sensor drops out.'],
  ['05', "What's exposed?", 'Buildings, roads, bridges, schools and hospitals in the predicted zone.'],
]

// Sentinel-2 L2A true-colour scenes (scripts/fetch_home_imagery.py); landscapes only, no people (Track B rule)
// Real flood photographs: Wikimedia Commons, CC BY-SA (resized/darkened here; adaptations shared under the same licence)
const IMG: Record<string, [string, string]> = {
  dharali: ['Dharali & Kheer Ganga fan, Uttarkashi', 'Sentinel-2 · 9 Nov 2025'], kedarnath: ['Mandakini valley, Kedarnath route', 'Sentinel-2 · 14 Dec 2024'],
  joshimath: ['Joshimath, Alaknanda–Dhauliganga', 'Sentinel-2 · 6 Dec 2024'], haridwar: ['The braided Ganga at Haridwar', 'Sentinel-2 · 19 Nov 2024'],
  haldwani: ['Gaula river fan, Haldwani', 'Sentinel-2 · 16 Dec 2024'],
  'real-rudraprayag-2013': ['Alaknanda–Mandakini confluence in spate, Rudraprayag, 21 Jun 2013', 'Photo: Mukerjee, CC BY-SA 3.0, Wikimedia Commons'],
  'real-broken-bridge': ['Riverbank buildings and footbridge undercut by the Mandakini, Rudraprayag, 2013', 'Photo: Mukerjee, CC BY-SA 3.0, Wikimedia Commons'],
  'real-uttarkashi-2013': ['The Bhagirathi in flood at Uttarkashi, 2013', 'Photo: sumit, CC BY-SA 4.0, Wikimedia Commons'],
  'real-tharali-road': ['Road in Tharali buried by slide material', 'Photo: Nitin Maletha, CC BY-SA 4.0, Wikimedia Commons'],
}

/** Full-width section over a darkened satellite scene; the image fades into the page at both edges. */
function Band({ img, children, className = '' }: { img: keyof typeof IMG; children: React.ReactNode; className?: string }) {
  return (
    <div className={`relative isolate overflow-hidden ${className}`}>
      <img src={`/img/home/${img}.webp`} alt="" loading="lazy" decoding="async" className="absolute inset-0 -z-10 h-full w-full object-cover opacity-60" />
      <div className="absolute inset-0 -z-10 bg-[#0b1d14]/70" />
      <div className="absolute inset-x-0 top-0 -z-10 h-40 bg-gradient-to-b from-[#0b1d14] to-transparent" />
      <div className="absolute inset-x-0 bottom-0 -z-10 h-40 bg-gradient-to-t from-[#0b1d14] to-transparent" />
      {children}
      <div className="pointer-events-none absolute bottom-3 right-4 max-w-[70%] text-right font-mono text-[10px] tracking-wide text-ink/50">{IMG[img][0]} · {IMG[img][1]}</div>
    </div>
  )
}

const LAYERS = [
  ['Hazard', 'Will flooding occur?', 'Multimodal prediction + uncertainty'],
  ['Inundation', 'Where, and how deep?', 'Extent, depth and forecast window'],
  ['Exposure', 'What could be affected?', 'Buildings, roads, critical assets'],
]

export default function Landing() {
  const snap = useData<Snapshot>('snapshot')
  const model = useData<ModelData>('model')
  const top = snap?.stations[0]

  return (
    <div className="landing-bg min-h-full">
      {/* HERO */}
      <section className="relative h-screen overflow-hidden">
        <img src="/img/home/hero-alaknanda.webp" alt="" fetchPriority="high" decoding="async" className="kenburns absolute inset-0 h-full w-full object-cover" />
        <img src="/img/home/real-uttarkashi-2013.webp" alt="" decoding="async" className="hero-fade absolute inset-0 h-full w-full object-cover" />
        <div className="pointer-events-none absolute inset-0 bg-[#06110c]/45" />
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-[#0b1d14] via-[#0b1d14]/65 to-transparent" />
        <div className="pointer-events-none absolute bottom-3 right-4 z-10 text-right font-mono text-[10px] tracking-wide text-ink/50">Alaknanda valley from Sentinel-2 (10 Jan 2025) ⇄ the Bhagirathi in flood at Uttarkashi, 2013 (photo: sumit, CC BY-SA 4.0, Wikimedia Commons)</div>
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-48 bg-gradient-to-t from-[#0b1d14] to-transparent" />

        <nav className="glass-strong absolute inset-x-4 top-4 z-30 flex items-center justify-between rounded-2xl px-4 py-2.5 md:inset-x-10">
          <div className="flex items-center gap-3"><img src="/prahar-mark.png" alt="" className="h-9 w-auto drop-shadow-[0_0_10px_rgba(79,179,240,.35)]" /><div><div className="font-display text-2xl leading-none tracking-wider text-white">PRAHAR</div><div className="font-mono text-[9px] tracking-[.25em] text-brand/80">PREDICT · PREPARE · PROTECT</div></div></div>
          <div className="hidden items-center gap-1 md:flex">
            <a href="#how" className="top-link">How it works</a>
            <a href="#layers" className="top-link">Layers</a>
            <a href="#numbers" className="top-link">Data</a>
            <Link to="/app/metrics" className="top-link">Accuracy</Link>
          </div>
          <Link to="/app" className="rounded-full bg-brand px-5 py-2 text-sm font-semibold text-bg shadow-[0_0_24px_#a3e63555] transition hover:brightness-110">Open console →</Link>
        </nav>

        <div className="relative z-10 flex h-full flex-col justify-center px-6 md:px-12">
          <div className="label rise">Uttarakhand · Flash-flood intelligence</div>
          <h1 className="mt-3 font-display uppercase leading-[0.92]">
            <span className="rise block text-[15vw] md:text-[7.4vw]" style={{ animationDelay: '.1s' }}>Flash floods</span>
            <span className="rise block text-[15vw] md:text-[7.4vw]" style={{ animationDelay: '.2s' }}>don't wait.</span>
            <span className="rise outline-text block text-[15vw] md:text-[7.4vw]" style={{ animationDelay: '.3s' }}>Neither should we.</span>
          </h1>
          <p className="rise mt-6 max-w-xl text-lg text-ink/80" style={{ animationDelay: '.45s' }}>
            We predict where a flash flood may hit, show how sure the model is, and turn the forecast into the
            buildings and roads that could be exposed.
          </p>
          <div className="rise mt-8 flex flex-wrap gap-3" style={{ animationDelay: '.55s' }}>
            <Link to="/app" className="rounded-full bg-brand px-6 py-3 font-semibold text-bg shadow-[0_0_30px_#a3e63555] hover:brightness-110">Replay a real event</Link>
            <a href="#how" className="rounded-full border border-ink/30 px-6 py-3 font-semibold hover:bg-ink/10">How it works</a>
          </div>
        </div>

        {top && snap && (
          <div className="glass rise absolute bottom-8 right-6 z-10 hidden w-80 rounded-xl p-4 md:block" style={{ animationDelay: '.8s' }}>
            <div className="flex items-center gap-2"><span className="h-2 w-2 animate-pulse rounded-full bg-severe" /><span className="label">Replay · {fmtTime(snap.replay_time)}</span></div>
            <div className="mt-3 flex items-end justify-between">
              <div><div className="text-sm text-mute">Highest-tier station</div><div className="text-xl font-semibold">{pretty(top.station)}</div><div className="text-xs text-mute">{top.district}</div></div>
              <div className="text-right"><div className="whitespace-nowrap font-mono text-4xl font-semibold" style={{ color: TIER_COLOR[top.tier] }}>{top.trigger === 'rainfall' ? `${(top.signals.rain_24h ?? 0).toFixed(0)} mm` : pct(top.p)}</div><div className="font-mono text-[10px] uppercase tracking-wider text-mute">{top.tier} · {top.trigger === 'rainfall' ? 'rain 24 h' : 'ML probability'}</div></div>
            </div>
            <div className="mt-2 text-xs text-mute">{snap.tier_counts.SEVERE + snap.tier_counts.EXTREME} stations at SEVERE or above · {snap.stations_reporting}/{snap.stations_total} reporting</div>
          </div>
        )}
      </section>

      {/* TRACK B headline result */}
      <section id="trackb" className="mx-auto max-w-6xl px-6 py-16"><TrackBCard /></section>

      {/* CHAIN */}
      <Band img="real-rudraprayag-2013"><section id="how" className="mx-auto max-w-6xl px-6 py-28">
        <div className="label">Beyond "probability = 82%"</div>
        <h2 className="mt-2 font-display text-5xl uppercase md:text-7xl">One question <span className="outline-text">leads to the next</span></h2>
        <div className="mt-12 grid gap-3 md:grid-cols-5">
          {CHAIN.map(([n, q, d]) => (
            <div key={n} className="glass-strong rounded-2xl p-6 transition duration-300 hover:-translate-y-1 hover:border-brand/40 hover:shadow-[0_12px_40px_rgba(163,230,53,.12)]">
              <div className="font-mono text-sm text-brand">{n}</div>
              <div className="mt-6 font-display text-2xl uppercase">{q}</div>
              <p className="mt-2 text-sm text-ink/75">{d}</p>
            </div>
          ))}
        </div>
      </section></Band>

      {/* LAYERS */}
      <Band img="kedarnath"><section id="layers" className="mx-auto max-w-6xl px-6 py-28">
        <h2 className="font-display text-5xl uppercase md:text-6xl">Three intelligence layers</h2>
        <div className="mt-10 space-y-3">
          {LAYERS.map(([name, q, d], i) => (
            <div key={name} className="glass-strong group flex items-center gap-6 rounded-2xl p-6 transition duration-300 hover:border-brand/50 hover:shadow-[0_12px_40px_rgba(163,230,53,.10)]">
              <div className="font-display text-6xl text-white/20 transition group-hover:text-brand">0{i + 1}</div>
              <div className="flex-1"><div className="font-display text-3xl uppercase">{name}</div><div className="text-ink/75">{q}</div></div>
              <div className="hidden text-right text-sm text-ink/70 md:block">{d}</div>
            </div>
          ))}
        </div>
      </section></Band>

      <Band img="dharali" className="h-[38vh]"><div /></Band>

      {/* HONEST NUMBERS */}
      {model && (
        <Band img="real-broken-bridge"><section id="numbers" className="mx-auto max-w-6xl px-6 py-28">
          <div className="glass-strong rounded-3xl">
          <div className="mx-auto grid max-w-6xl gap-8 px-6 py-16 md:grid-cols-4">
            {[
              [model.dataset.rows.toLocaleString(), 'station-hours fused'],
              [model.dataset.stations, 'rain gauges across ' + model.dataset.districts + ' districts'],
              [model.dataset.landslides.toLocaleString(), 'mapped landslides as terrain signal'],
              [model.fusion.length, 'feature sets tested on held-out flood episodes'],
            ].map(([v, l]) => (
              <div key={String(l)}><div className="font-display text-6xl text-white">{v}</div><div className="mt-1 text-sm text-ink/75">{l}</div></div>
            ))}
          </div>
          </div>
        </section></Band>
      )}

      <Band img="real-tharali-road"><footer className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-4 px-6 py-20 md:flex-row md:items-center">
        <div className="max-w-lg space-y-2 text-xs text-ink/70">
          <p>Decision-support prototype. Outputs are model estimates of exposure, not damage, casualty or evacuation decisions.</p>
          <p className="text-mute">Imagery: contains modified Copernicus Sentinel data 2024–2025 (Sentinel-2 L2A via Earth Search, AWS Open Data). Photographs from Wikimedia Commons by Mukerjee (CC BY-SA 3.0), sumit and Nitin Maletha (CC BY-SA 4.0); resized and darkened, shared under the same licences.</p>
        </div>
        <Link to="/app" className="rounded-full bg-ink px-6 py-3 font-semibold text-bg">Open console →</Link>
      </footer></Band>
    </div>
  )
}
