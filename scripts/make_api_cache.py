"""Small startup cache for the API engine: the last 1440 hourly rows per station (all the engine ever reads).
Keeps the backend inside Render's 512 MB free tier. Run after rebuilding the dataset: python scripts/make_api_cache.py"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
src = ROOT / "data/processed/final/uttarakhand_flash_flood_ml_dataset.parquet"
ds = pd.read_parquet(src)
tail = ds.sort_values("datetime").groupby("station").tail(24 * 60).reset_index(drop=True)
tail.to_parquet(ROOT / "data/processed/final/api_engine_cache.parquet", index=False)
print(len(ds), "->", len(tail), "rows")
