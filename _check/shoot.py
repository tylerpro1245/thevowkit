#!/usr/bin/env python3
"""Render every page at phone and desktop widths and save PNGs for visual inspection."""
import pathlib, sys
from playwright.sync_api import sync_playwright

OUT = pathlib.Path("/opt/data/venture/site/_check/shots")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:8788"

PAGES = {
    "home": "/",
    "guide": "/guides/getting-married-in-mexico/",
    "kits": "/kits/",
    "kit-mexico": "/kits/mexico-destination-wedding-planner/",
    "kit-program": "/kits/bilingual-wedding-program/",
    "about": "/about/",
    "ask": "/ask/",
    "404": "/nope",
}
VIEWS = {"phone": (390, 844), "desk": (1280, 900)}

with sync_playwright() as p:
    b = p.chromium.launch()
    for vname, (w, h) in VIEWS.items():
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2)
        pg = ctx.new_page()
        errs = []
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        for name, path in PAGES.items():
            pg.goto(BASE + path, wait_until="networkidle")
            pg.screenshot(path=str(OUT / f"{name}-{vname}.png"), full_page=(vname == "desk"))
            pg.screenshot(path=str(OUT / f"{name}-{vname}-fold.png"), full_page=False)
            # horizontal-overflow check: nothing should scroll sideways on a phone
            ow = pg.evaluate("document.documentElement.scrollWidth")
            iw = pg.evaluate("document.documentElement.clientWidth")
            flag = "  <-- H-OVERFLOW" if ow > iw + 1 else ""
            print(f"{vname:5} {name:12} scrollW={ow} clientW={iw}{flag}")
        ctx.close()
        if errs:
            print(f"  console errors ({vname}):", errs[:5])
    b.close()
print("shots ->", OUT)
