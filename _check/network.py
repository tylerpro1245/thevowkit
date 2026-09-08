#!/usr/bin/env python3
"""Confirm every network request each page makes returns 200 and is same-origin."""
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8788"
PAGES = ["/", "/guides/getting-married-in-mexico/", "/kits/",
         "/kits/mexico-destination-wedding-planner/", "/kits/bilingual-wedding-program/",
         "/about/", "/ask/"]

bad = []
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 900})
    pg = ctx.new_page()
    for path in PAGES:
        reqs = []
        pg.on("response", lambda r: reqs.append((r.status, r.url)))
        pg.goto(BASE + path, wait_until="networkidle")
        pg.remove_listener("response", pg.listeners("response")[0]) if False else None
        offsite = [u for s, u in reqs if not u.startswith(BASE)]
        errs = [(s, u) for s, u in reqs if s >= 400]
        print(f"{path:45} {len(reqs):>2} requests  {len(offsite)} off-site  {len(errs)} failed")
        for s, u in errs:
            bad.append(f"{path}: {s} {u}")
        for u in offsite:
            bad.append(f"{path}: OFF-SITE REQUEST {u}")
        reqs.clear()
    b.close()

print()
if bad:
    print("PROBLEMS:")
    for x in bad:
        print("  ✗", x)
    raise SystemExit(1)
print("PASS — every page loads with zero failed requests and zero third-party requests.")
