"""Capture Space-mode (Track B) screenshots of the new features from vite preview on :4173.
Run: python scripts/capture_space.py
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

        def shot(name, wait=1.5):
            time.sleep(wait); pg.screenshot(path=str(OUT / f"{name}.png")); print("saved", name, flush=True)

        def to(text, wait=1.5):
            pg.get_by_text(text, exact=False).first.scroll_into_view_if_needed(); time.sleep(wait)

        pg.goto(BASE + "/app/space", wait_until="load", timeout=90000); time.sleep(8)
        pg.get_by_role("button", name="Trishuli", exact=True).click(); time.sleep(12)
        shot("17_trishuli_space_mode")
        to("Checked against Copernicus EMS"); shot("18_trishuli_vs_EMSR927_check")
        to("Rescue priorities"); shot("19_trishuli_rescue_priorities_landing_sites")
        # flood-path tracer: click an upstream point near Timure (top of the map)
        pg.get_by_role("button", name="Trace a flood path").click(); time.sleep(0.5)
        canvas = pg.locator(".maplibregl-canvas").first
        canvas.scroll_into_view_if_needed(); time.sleep(1)
        bb = canvas.bounding_box()
        pg.mouse.click(bb["x"] + bb["width"] / 2 + 60, bb["y"] + 70); time.sleep(2)
        pg.evaluate("window.scrollBy(0, 260)"); shot("20_trishuli_flood_path_tracer")
        # Sentinel-2 before/after slider
        pg.get_by_label("Sentinel-2", exact=True).check(); time.sleep(3)
        sl = pg.locator("input[type=range]").first
        sl.fill("0"); time.sleep(3); shot("24_trishuli_s2_before")
        sl.fill("1"); time.sleep(3); shot("25_trishuli_s2_after")
        pg.get_by_label("Sentinel-2", exact=True).uncheck()
        pg.get_by_role("button", name="नेपाली").click(); to("नेपाली सारांश", 1); shot("26_trishuli_sitrep_nepali")
        pg.get_by_role("button", name="Dharali", exact=True).click(); time.sleep(9)
        shot("21_dharali_space_mode_s2_fusion")
        to("Rescue priorities"); shot("22_dharali_rescue_priorities")
        pg.get_by_role("button", name="हिन्दी").click(); to("हिन्दी सारांश", 1); shot("23_sitrep_hindi")
        pg.goto(BASE + "/", wait_until="load", timeout=90000); time.sleep(5)
        pg.locator("#trackb").scroll_into_view_if_needed(); time.sleep(2); shot("27_landing_trackb_results")
        b.close()


if __name__ == "__main__":
    main()
