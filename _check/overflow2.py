#!/usr/bin/env python3
"""Find the REAL horizontal-overflow culprits: elements that stick out past the
viewport and are NOT inside a scroll container (where sticking out is intended)."""
from playwright.sync_api import sync_playwright
import sys

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8788/guides/getting-married-in-mexico/"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_context(viewport={"width": 390, "height": 844}).new_page()
    pg.goto(URL, wait_until="networkidle")
    bad = pg.evaluate("""() => {
      const vw = document.documentElement.clientWidth;
      const out = [];
      const inScroller = el => {
        for (let n = el.parentElement; n; n = n.parentElement) {
          const ox = getComputedStyle(n).overflowX;
          if (ox === 'auto' || ox === 'scroll' || ox === 'hidden') return true;
        }
        return false;
      };
      document.querySelectorAll('body *').forEach(el => {
        const cs = getComputedStyle(el);
        if (cs.position === 'absolute' || cs.position === 'fixed') return;
        const r = el.getBoundingClientRect();
        if (r.width === 0) return;
        if ((r.right > vw + 1 || r.left < -1) && !inScroller(el)) {
          out.push({tag: el.tagName.toLowerCase(),
                    cls: (el.className||'').toString().slice(0,40),
                    left: Math.round(r.left), right: Math.round(r.right),
                    w: Math.round(r.width),
                    text: (el.textContent||'').trim().slice(0,60)});
        }
      });
      return out;
    }""")
    for e in bad[:20]:
        print(f"{e['tag']:7} .{e['cls']:20} L{e['left']:5} R{e['right']:5} W{e['w']:5} | {e['text']}")
    print("REAL overflow culprits:", len(bad))
    print("scrollWidth:", pg.evaluate("document.documentElement.scrollWidth"),
          "clientWidth:", pg.evaluate("document.documentElement.clientWidth"))
    b.close()
