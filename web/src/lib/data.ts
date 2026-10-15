import { useEffect, useState, useSyncExternalStore } from 'react'

export type Tier = 'NORMAL' | 'WATCH' | 'ALERT' | 'SEVERE' | 'EXTREME'
export type Station = { station: string; district: string; lat: number; lon: number; kind: 'rain' | 'river' }
export type StationSnap = {
  station: string; district: string; time: string; p: number; tier: Tier
  predicted: number; observed: number | null; signals: Record<string, number | null>
  raw_score: number; tier_ml?: Tier; tier_rain?: Tier; trigger?: 'ml' | 'rainfall' | 'none'; confidence: number; credibility: number; cp_set_90: 'FLOOD' | 'NO_FLOOD' | 'UNCERTAIN' | 'EMPTY'
  drivers: { feature: string; shap: number; value: number }[]
}
export type Source = { name: string; status: 'available' | 'missing' | 'pending'; detail: string }
export type Snapshot = {
  replay_time: string; model: string; peak_p: number; peak_p_3h_ago: number | null
  stations_reporting: number; stations_total: number; tier_counts: Record<Tier, number>
  stations: StationSnap[]; sources: Source[]
  base_rate: number
  conformal: { calibration_positives: number; test_positives: number; brier_raw: number; brier_calibrated: number
    coverage: { nominal: number; coverage_all: number; coverage_flood: number | null; coverage_no_flood: number; share_uncertain: number }[] }
}
export type TimelinePt = { t: string; max_p: number; mean_p: number; q10: number; q90: number; n: number; observed: number }
export type ModelData = {
  comparison: Record<string, number | string>[]
  final_experiment: string
  coverage: { month: string; rain_stations: number; discharge_gauges: number; flood_events: number }[]
  windows: Record<string, { start: string; end: string | null; sources?: string; used_for: string }>
  normalization: { fit_window: { start: string; end: string } | null; features: { feature: string; method: string; center: number; scale: number }[] }
  robustness: { scenario: string; kind: string; roc_auc: number; pr_auc: number; mean_abs_score_change: number; flood_rows_mean_score: number }[]
  lead: { alarm_threshold: number; hourly_false_alarm_rate: number; events_evaluated: number; events_detected: number; median_lead_time_h: number | null }
  warning: { base_rate: number; thresholds: Record<string, number>; test_alert_recall: number; test_alert_precision: number; test_false_alarm_rate: number }
  fusion: { label: string; features: number; folds: number; positives: number; pooled_roc_auc: number; pooled_pr_auc: number; base_rate: number; mean_fold_roc_auc: number; min_fold_roc_auc: number; final: boolean }[]
  importance: { feature: string; importance: number; group: string }[]
  importance_groups: { group: string; importance: number }[]
  dataset: { rows: number; stations: number; districts: number; start: string; end: string; positives: number; labelled_rows: number; label_end: string; landslides: number; flood_events: number }
}
export type Events = {
  floods: { UEI: string; start: string; cause: string; districts: string; fatalities: number | null; lat: number | null; lon: number | null }[]
  landslides_by_district: Record<string, number>
  landslide_points: [number, number][]
}

export const TIER_COLOR: Record<Tier, string> = {
  NORMAL: '#3ddc97', WATCH: '#f5d547', ALERT: '#ff9f1c', SEVERE: '#ff4d2e', EXTREME: '#e0115f',
}
export const TIERS: Tier[] = ['NORMAL', 'WATCH', 'ALERT', 'SEVERE', 'EXTREME']

const cache = new Map<string, Promise<unknown>>()
let pending = 0
const listeners = new Set<() => void>()
const bump = (d: number) => { pending += d; listeners.forEach(l => l()) }
let cursor: { lat: number; lon: number } | null = null
const cursorL = new Set<() => void>()
export const setCursor = (c: { lat: number; lon: number } | null) => { cursor = c; cursorL.forEach(l => l()) }
export const useCursor = () => useSyncExternalStore(l => { cursorL.add(l); return () => { cursorL.delete(l) } }, () => cursor)

export const usePending = () => useSyncExternalStore(l => { listeners.add(l); return () => { listeners.delete(l) } }, () => pending)

// Data source: the FastAPI backend when VITE_API_URL is set (e.g. "/api" via the dev proxy), else static files.
const API = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '')
export const DATA_BASE = API ? `${API}/data` : '/data'
export const TILE_INDEX_URL = API ? `${API}/impact/tiles/index` : '/data/bld/index.json'
export const tileUrl = (z: number, x: number, y: number) => (API ? `${API}/impact/tiles/${z}/${x}/${y}` : `/data/bld/${z}/${x}/${y}.json`)

/** fetch JSON while counting it as in-flight work (drives the >200 ms loading overlay) */
export function fetchTracked<T>(url: string): Promise<T> {
  bump(1)
  return fetch(url).then(r => r.json() as Promise<T>).finally(() => bump(-1))
}

function load<T>(name: string): Promise<T> {
  if (!cache.has(name)) {
    bump(1)
    cache.set(name, fetch(`${DATA_BASE}/${name}${API ? '' : name === 'buildings' || name === 'landmarks' ? '.geojson' : '.json'}`)
      .then(r => r.json()).finally(() => bump(-1)))
  }
  return cache.get(name) as Promise<T>
}

export function useData<T>(name: 'stations' | 'snapshot' | 'timeline' | 'model' | 'events' | 'impact' | 'buildings' | 'landmarks' | 'metrics' | 'system' | 'district_watch' | 'space_index' | `space_${string}`) {
  const [d, setD] = useState<T | null>(null)
  useEffect(() => { load<T>(name).then(setD) }, [name])
  return d
}

export const pct = (p: number | null | undefined, digits = 0) => (p == null ? '—' : `${(p * 100).toFixed(digits)}%`)
export const fmtTime = (iso: string) =>
  new Date(iso).toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
export const pretty = (s: string) => s.replace(/_\d+$/, '').replace(/_/g, ' ')

export type Asset = { name: string; lat: number; lon: number; dist_water_m: number; type: string }
export type CoveragePt = { station: string; lat: number; lon: number; r_km?: number; src?: number }
export type Coverage = { radius_km: number; reporting: CoveragePt[]; offline: CoveragePt[] }
export type Impact = {
  coverage?: Coverage
  method: string; replay_time: string; stations: string[]; buildings_in_radius: number; buildings_exposed: number
  by_class: Record<string, number>; by_station: { station: string; buildings: number; exposed: number; mean_score: number; lon?: number; lat?: number }[]
  station_p: { station: string; p: number; src?: number; tier?: string; last?: string | null; rank?: number | null }[]
  roads: number; bridges: Asset[]; schools: Asset[]; health: Asset[]; sources: string[]
}

export type Pod = { n: number; detected: number; POD: number | null; ci95: [number | null, number | null] }
export type Metrics = {
  hour_level: (Record<string, number | string> & { model: string; split: string; precision: number; recall: number; f1: number; threshold: number })[]
  confusion: Record<string, [[number, number], [number, number]]>
  pr_curve: { threshold: number; precision: number; recall: number; f1: number | null }[]
  event_detection: { events_evaluated: number; events_detected: number; median_lead_time_h: number | null; hourly_false_alarm_rate: number }
  events: { district: string; event_start: string; stations: number; detected: boolean; lead_time_h: number | null }[]
  warning_levels: Record<string, { precision: number; recall: number; f1: number; false_alarm_rate: number; alerts: number }>
  verification?: {
    contingency: { unit: string; split: string; level: string; layer: string; n: number; events: number; base_rate: number; tp: number; fp: number; fn: number; tn: number
      POD: number | null; FAR: number | null; POFD: number | null; CSI: number | null; ETS: number | null; HSS: number | null; bias: number | null; ci95: Record<string, [number, number]> }[]
    probabilistic: { 'station-hour': { brier: number; brier_climatology: number; BSS: number }; reliability_station_hour: { mean_pred: number; obs_freq: number; n: number }[]; ECE_station_hour: number }
    lead_time: { events: number; warned_before: number; baseline_only: number; missed: number; median_lead_h: number | null
      events_table: { district: string; event_day: string; status: string; lead_h_before_event_day: number | null }[] }
    relative_value: { alpha: number; value: number }[]
  }
  external_validation?: {
    summary: { events: number; events_with_station_data: number; hybrid_alert_detected: number; period?: string
      pod_hybrid_alert?: Pod; pod_ml_alert?: Pod; pod_rain_alert?: Pod; by_confidence?: Record<string, Pod>; by_severity?: Record<string, Pod>
      alert_burden?: { monsoon: number; alert_district_days: number; near_documented_event: number; share_near_event: number }[] }
    events: { event_id: string; date: string; district: string; place: string | null; date_confidence?: string; severity?: string; sources?: string
      stations_reporting: number; hybrid_alert: boolean | null; hybrid_severe: boolean | null; ml_alert: boolean | null; rain_alert: boolean | null; max_tier: string; trigger_at_max: string | null; lead_h_to_day_end: number | null; source_url: string }[]
  }
  labels?: {
    sources?: { events: number; district_days: number; by_year: Record<string, number>; by_source_family: Record<string, number>; corroborated_events: number }
    audit?: { summary: { imd_events: number; sandrp_events: number; sandrp_only_events: number; imd_days_confirmed_by_sandrp: number; imd_district_days: number
        sandrp_only_by_split: Record<string, number>; sandrp_only_valtest_alerted_by_hybrid: string; gate: { share: number; passed: boolean } }
      by_district: { district: string; imd_days: number; sandrp_days: number; matched_imd_days: number; sandrp_only_days: number }[] }
    experiment?: { decision: { adopt_v2: boolean; v2_on_v1_truth_ok: boolean; v2_on_v2_truth_ok: boolean; event_cv_ok: boolean }
      event_cv: Record<string, { pooled_roc_auc: number; pooled_pr_auc: number; base_rate: number; folds: number }>
      xgboost_grid: { trained_on: string; scored_on: string; pr_auc: number; roc_auc: number; f1: number; dd_POD: number | null; dd_FAR: number | null; dd_CSI: number | null; dd_CSI_ci95: [number, number] }[] }
    before_after?: { model: string; roc_auc_before: number; roc_auc_after: number; pr_auc_before: number; pr_auc_after: number; f1_before: number; f1_after: number; mcc_before: number; mcc_after: number }[]
    district_day?: { model: string; test_roc_auc: number; test_pr_auc: number; base_rate: number; csi: number | null; hybrid_csi: number | null; external: string; adopted: boolean }
    model_upgrade?: { e1: { roc_xgb: number; roc_ens: number; adopt: boolean }; e2: { csi_current: number; csi_fitted: number; median_event_24h: number; adopt: boolean }; e3: { external_model: number; external_prior: number; chance: number; ranking: boolean } }
    rain_rule_tuning?: { adopted: boolean; rule: Record<string, number | boolean>; best_candidate: Record<string, number | boolean> }
  }
  splits: Record<'train' | 'validation' | 'test', { start: string; end: string; rows: number; positives: number; stations: number }>
}
export type System = {
  checked_at: string; local_api_running: boolean
  external: { name: string; ok: boolean; status: number | null; ms: number; error?: string }[]
  local_api: { name: string; ok: boolean; ms: number }[]
  latency: { path: string; variant: string; p50_ms: number | null; p95_ms: number | null; bytes?: number | null }[]
  notebook_runs: { batch: string; status: string; seconds: number }[]
}
