import { useMemo, useState } from 'react'

export type Place = { name: string; lon: number; lat: number; kind?: string }

// Type-ahead place search: prefix matches first, then substring; Enter or click flies the map there.
export default function PlaceSearch({ places, onPick, placeholder = 'Search a city, town or village…', className = '' }: {
  places: Place[]; onPick: (p: Place) => void; placeholder?: string; className?: string
}) {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [i, setI] = useState(0)
  const hits = useMemo(() => {
    const s = q.trim().toLowerCase()
    if (s.length < 2) return []
    const seen = new Set<string>()
    return places
      .filter(p => p.name && p.name.toLowerCase().includes(s))
      .sort((a, b) => Number(!a.name.toLowerCase().startsWith(s)) - Number(!b.name.toLowerCase().startsWith(s)) || a.name.length - b.name.length)
      .filter(p => { const k = `${p.name}|${p.lon.toFixed(2)}`; if (seen.has(k)) return false; seen.add(k); return true })
      .slice(0, 8)
  }, [q, places])
  const pick = (p: Place) => { onPick(p); setQ(p.name); setOpen(false) }
  return (
    <div className={`${className || "relative"} w-72`}>
      <input value={q} placeholder={placeholder}
        onChange={e => { setQ(e.target.value); setOpen(true); setI(0) }} onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={e => {
          if (e.key === 'ArrowDown') { setI(x => Math.min(x + 1, hits.length - 1)); e.preventDefault() }
          else if (e.key === 'ArrowUp') { setI(x => Math.max(x - 1, 0)); e.preventDefault() }
          else if (e.key === 'Enter' && hits[i]) pick(hits[i])
          else if (e.key === 'Escape') setOpen(false)
        }}
        className="w-full rounded-lg border border-line bg-black/75 px-3 py-2 text-sm text-ink shadow-lg outline-none backdrop-blur placeholder:text-mute focus:border-brand" />
      {open && hits.length > 0 && (
        <ul className="absolute z-20 mt-1 max-h-72 w-full overflow-y-auto rounded-lg border border-line bg-black/90 py-1 text-sm shadow-xl backdrop-blur">
          {hits.map((p, k) => (
            <li key={`${p.name}${p.lon}`} onMouseDown={() => pick(p)} onMouseEnter={() => setI(k)}
              className={`flex cursor-pointer justify-between gap-2 px-3 py-1.5 ${k === i ? 'bg-brand/15 text-brand' : 'text-ink'}`}>
              <span className="truncate">{p.name}</span>{p.kind && <span className="shrink-0 text-xs text-mute">{p.kind}</span>}
            </li>))}
        </ul>)}
    </div>
  )
}
