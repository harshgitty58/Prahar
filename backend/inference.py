"""
Low-latency inference engine, loaded once at API startup.

Per request the work is: O(1) feature update per station (src/online_features.py) → one XGBoost predict
→ Venn-Abers calibration by table lookup (np.interp over a precomputed grid instead of isotonic refits)
→ conformal p-values by binary search on pre-sorted calibration scores → hybrid tier.
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.conformal import venn_abers
from src.data_loader import FEATURE_EXPERIMENTS, FINAL_EXPERIMENT
from src.online_features import StationState
from src.warning_levels import TIERS, assign

ROOT = Path(__file__).resolve().parents[1]
STATIC_COLS = ["district", "latitude", "longitude", "is_landslide_hotspot", "district_flood_severity_index"]


class Engine:
    def __init__(self):
        self.features = FEATURE_EXPERIMENTS[FINAL_EXPERIMENT]
        self.model = joblib.load(ROOT / "models/xgboost/model.joblib")
        # read only the columns the API needs (the full table is ~400 MB in memory; Render's free tier has 512 MB)
        path = ROOT / "data/processed/final/uttarakhand_flash_flood_ml_dataset.parquet"
        import pyarrow.parquet as pq
        have = set(pq.read_schema(path).names)
        static_cols = [c for c in set(self.features + STATIC_COLS) if c in have and not c.startswith(("rain_", "api_"))]
        cols = sorted({"station", "datetime", "rain_1h", *static_cols} & have)
        cache = ROOT / "data/processed/final/api_engine_cache.parquet"   # per-station last 1440 h (scripts/make_api_cache.py)
        ds = pd.read_parquet(cache if cache.exists() else path, columns=cols)
        for c in ds.select_dtypes("float64").columns:
            ds[c] = ds[c].astype("float32")
        last = ds.sort_values("datetime").groupby("station").tail(1).set_index("station")
        # static (non-rain) inputs per station = latest known values
        self.static = last[[c for c in set(self.features + STATIC_COLS) if c in last and not c.startswith(("rain_", "api_"))]]
        # per-station history indexed once, so warming a station is a dict lookup + a 96-row replay (no full-table scan)
        self.history = {st: g.sort_values("datetime")[["datetime", "rain_1h"]].tail(24 * 60).reset_index(drop=True)
                        for st, g in ds.groupby("station")}
        del ds, last
        cal = pd.read_csv(ROOT / "results/conformal/calibration_scores.csv")
        s, y = cal["score"].to_numpy(), cal["y"].to_numpy()
        self.grid = np.unique(np.quantile(s, np.linspace(0, 1, 400)))
        self.g0, self.g1 = venn_abers(s, y, self.grid)
        cal_p = cal["p_calibrated"].to_numpy()
        # sorted non-conformity scores per class (class 1: 1-p, class 0: p)
        self.nc = {1: np.sort(1 - cal_p[y == 1]), 0: np.sort(cal_p[y == 0])}
        w = json.loads((ROOT / "results/warning_levels/warning_thresholds.json").read_text())
        self.dfsi_median, self.thresholds = w["dfsi_median"], w["thresholds"]
        self.rain_rule = w.get("rain_rule")  # tuned station-local rainfall rule (src/tier_tuning.py); None = default
        self.states: dict[str, StationState] = {}

    # ---- state ---------------------------------------------------------------------------------------------
    def warm_station(self, station: str, until: pd.Timestamp | None = None, hours: int = 96) -> StationState:
        """Replay the last `hours` of history into a fresh state (needed once per station)."""
        h = self.history.get(station)
        if h is None:
            raise KeyError(station)
        if until is not None:
            h = h[h["datetime"] <= until]
        st = StationState()
        for t, r in zip(h["datetime"].tail(hours), h["rain_1h"].tail(hours)):
            st.update(t, r)
        self.states[station] = st
        return st

    # ---- scoring -------------------------------------------------------------------------------------------
    def _calibrate(self, raw: np.ndarray):
        p0, p1 = np.interp(raw, self.grid, self.g0), np.interp(raw, self.grid, self.g1)
        p = p1 / (1 - p0 + p1)
        pv = np.empty((len(p), 2))
        for c, scores in self.nc.items():
            test = 1 - p if c == 1 else p
            pv[:, c] = (len(scores) - np.searchsorted(scores, test, side="left") + 1) / (len(scores) + 1)
        return p, np.minimum(p0, p1), np.maximum(p0, p1), pv

    def score(self, rows: pd.DataFrame) -> pd.DataFrame:
        raw = self.model.predict_proba(rows[self.features])[:, 1]
        p, lo, hi, pv = self._calibrate(raw)
        out = rows.copy()
        out["raw_score"], out["p_calibrated"], out["va_lower"], out["va_upper"] = raw, p, lo, hi
        out["confidence"], out["credibility"] = 1 - pv.min(1), pv.max(1)
        inc0, inc1 = pv[:, 0] > 0.10, pv[:, 1] > 0.10
        out["cp_set_90"] = np.select([inc0 & inc1, inc1, inc0], ["UNCERTAIN", "FLOOD", "NO_FLOOD"], "EMPTY")
        return assign(out, self.dfsi_median, self.thresholds, self.rain_rule)

    def predict(self, station: str, readings: list[dict], overrides: dict | None = None) -> dict:
        """readings: [{"datetime": ..., "rain_mm": ...}, ...] in time order (appended to the station's state)."""
        if station not in self.static.index:
            raise KeyError(station)
        st = self.states.get(station) or self.warm_station(station, until=pd.Timestamp(readings[0]["datetime"]) - pd.Timedelta(hours=1) if readings else None)
        feats = st.features()
        for r in readings:
            feats = st.update(pd.Timestamp(r["datetime"]), r.get("rain_mm", 0.0))
        row = {**self.static.loc[station].to_dict(), **feats, **(overrides or {}), "station": station}
        res = self.score(pd.DataFrame([row])).iloc[0]
        keep = ["station", "district", "raw_score", "p_calibrated", "va_lower", "va_upper", "confidence", "credibility",
                "cp_set_90", "tier", "tier_ml", "tier_rain", "trigger", "rain_1h", "rain_24h", "rain_72h"]
        out = {k: (v.item() if hasattr(v, "item") else v) for k, v in res[keep].items()}
        out["as_of"] = str(st.last_time) if st.last_time is not None else None
        return out


__all__ = ["Engine", "TIERS"]
