#!/usr/bin/env python3
"""Find which element overflows the viewport horizontally."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_context(viewport={"width": 390, "height": 844}).new_page()
    pg.goto("http://127.0.0.1:8788/guides/getting-married-in-mexico/", wait_until="networkidle")
    bad = pg.evaluate("""() => {
      const vw = document.documentElement.clientWidth;
      const out = [];
      document.querySelectorAll('*').forEach(el => {
        const r = el.getBoundingClientRect();
        if (r.right > vw + 1 || r.left < -1) {
          out.push({
            tag: el.tagName.toLowerCase(),
            cls: el.className && el.className.toString().slice(0,60),
            id: el.id,
            left: Math.round(r.left), right: Math.round(r.right),
            w: Math.round(r.width),
            text: (el.textContent||'').trim().slice(0,70)
          });
        }
      });
      return out;
    }""")
    for e in bad[:25]:
        print(f"{e['tag']:6} .{e['cls']:22} #{e['id']:10} L{e['left']:5} R{e['right']:5} W{e['w']:5} | {e['text']}")
    print("total overflowing elements:", len(bad))
    b.close()
