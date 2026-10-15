"""Capture submission screenshots of the web app (vite preview on :4173) with Playwright driving the installed Edge.
Run: python scripts/capture_screens.py
"""
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "submission media"
BASE = "http://localhost:4173"


def main():
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        pg = b.new_page(viewport={"width": 1600, "height": 900}, device_scale_factor=1.5)

        def go(path, wait=3.5):
            pg.goto(BASE + path, wait_until="networkidle"); time.sleep(wait)

        def shot(name, wait=0.0):
            time.sleep(wait); pg.screenshot(path=str(OUT / f"{name}.png")); print("saved", name, flush=True)

        def scroll_to(sel, wait=1.5):
            pg.locator(sel).first.scroll_into_view_if_needed(); time.sleep(wait)

        go("/", 4); shot("01_home_hero")
        pg.evaluate("window.scrollBy(0, 0)"); time.sleep(6); shot("02_home_hero_flood_photo")   # hero cross-fades to the 2013 photo
        scroll_to("#how"); shot("03_home_how_it_works")
        scroll_to("#layers"); shot("04_home_layers")
        go("/app/overview", 5); shot("05_overview")
        go("/app/map", 8); shot("06_risk_map")
        go("/app/impact", 6)
        try:
            pg.get_by_text("Haldwani", exact=False).first.click(); time.sleep(9)
        except Exception as e:  # noqa: BLE001
            print("impact click skipped:", type(e).__name__)
        shot("07_impact_buildings_haldwani")
        go("/app/uncertainty", 4); shot("08_uncertainty")
        go("/app/events", 4); shot("09_events")
        go("/app/model", 4); shot("10_model")
        go("/app/metrics", 4); shot("11_metrics")
        try:
            pg.get_by_text("Ground truth", exact=False).first.scroll_into_view_if_needed(); time.sleep(1.5)
        except Exception:  # noqa: BLE001
            pg.mouse.wheel(0, 900); time.sleep(1.5)
        shot("12_metrics_ground_truth")
        go("/app/system", 4); shot("13_system")
        go("/app/space", 9); shot("14_space_mode_dharali")
        try:
            pg.get_by_text("Who is cut off", exact=False).first.scroll_into_view_if_needed(); time.sleep(1.5)
        except Exception:  # noqa: BLE001
            pg.mouse.wheel(0, 1100); time.sleep(1.5)
        shot("15_space_cutoff_model_card")
        b.close()


if __name__ == "__main__":
    main()
