#!/usr/bin/env python3
"""
validate.py — self-contained checker for the thevowkit.com static site.

Runs three passes and exits non-zero on any failure:

  1. HTML well-formedness — every tag opened is closed, in order, with no
     stray closers. Uses html.parser (stdlib) so there is nothing to install.
  2. Internal link resolution — every href/src that points inside the site
     resolves to a real file on disk, and every in-page #anchor exists in the
     page it points at (including cross-page anchors like /guides/x/#sources).
  3. Structural sanity — required meta tags, one <h1> per page, no empty
     hrefs, no accidental placeholder text left behind.

Usage:  python3 validate.py [site_dir]
"""

import os
import re
import sys
from html.parser import HTMLParser
from urllib.parse import urlparse, unquote

SITE = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                       os.path.dirname(os.path.abspath(__file__)))

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}

# Text that must never survive into production.
PLACEHOLDERS = [r"\blorem\b", r"\bipsum\b", r"\bTODO\b", r"\bFIXME\b",
                r"\bXXX\b", r"\{\{", r"\bTBD\b", r"PLACEHOLDER"]


class Checker(HTMLParser):
    """Tracks tag balance and collects ids, hrefs, srcs and headings."""

    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.stack = []
        self.errors = []
        self.ids = set()
        self.links = []      # (href, line)
        self.assets = []     # (src, line)
        self.h1 = 0
        self.metas = set()
        self.title = False
        self.imgs_without_alt = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            if a["id"] in self.ids:
                self.errors.append(f"duplicate id #{a['id']} (line {self.getpos()[0]})")
            self.ids.add(a["id"])
        if "href" in a:
            self.links.append((a["href"], self.getpos()[0]))
        if "src" in a:
            self.assets.append((a["src"], self.getpos()[0]))
        if tag == "h1":
            self.h1 += 1
        if tag == "title":
            self.title = True
        if tag == "meta":
            if a.get("charset"):
                self.metas.add("charset")
            n = a.get("name", "")
            if n in ("viewport", "description"):
                self.metas.add(n)
        if tag == "img":
            if not a.get("alt", "").strip():
                self.imgs_without_alt += 1
        if tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack:
            self.errors.append(f"</{tag}> with nothing open (line {self.getpos()[0]})")
            return
        if self.stack[-1][0] == tag:
            self.stack.pop()
            return
        # Look for the tag further down the stack -> something was left unclosed.
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                unclosed = [f"<{t}> (line {ln})" for t, ln in self.stack[i + 1:]]
                self.errors.append(
                    f"</{tag}> at line {self.getpos()[0]} closes out of order; "
                    f"still open: {', '.join(unclosed)}")
                del self.stack[i:]
                return
        self.errors.append(f"</{tag}> never opened (line {self.getpos()[0]})")

    def finish(self):
        for t, ln in self.stack:
            self.errors.append(f"<{t}> opened at line {ln} and never closed")
        return self.errors


def html_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {"_check", ".git"}]
        for fn in sorted(filenames):
            if fn.endswith(".html"):
                yield os.path.join(dirpath, fn)


def url_to_disk(url_path):
    """Map a site-absolute URL path to a file on disk, honouring dir indexes."""
    p = unquote(url_path).lstrip("/")
    cand = os.path.join(SITE, p)
    if p == "" or url_path.endswith("/"):
        return os.path.join(cand, "index.html")
    if os.path.isdir(cand):
        return os.path.join(cand, "index.html")
    return cand


def main():
    pages = list(html_files(SITE))
    if not pages:
        print("FAIL: no HTML files found under", SITE)
        return 1

    parsed = {}
    failures = []

    # --- pass 1: parse + well-formedness -------------------------------
    for path in pages:
        raw = open(path, encoding="utf-8").read()
        c = Checker(path)
        c.feed(raw)
        c.close()
        errs = c.finish()
        parsed[path] = (c, raw)
        rel = os.path.relpath(path, SITE)
        for e in errs:
            failures.append(f"[html] {rel}: {e}")

    # --- pass 2: links + anchors ---------------------------------------
    for path, (c, raw) in parsed.items():
        rel = os.path.relpath(path, SITE)
        for href, line in c.links:
            if not href.strip():
                failures.append(f"[link] {rel}:{line}: empty href")
                continue
            u = urlparse(href)
            if u.scheme in ("http", "https", "mailto", "tel"):
                continue          # external, checked separately
            if href.startswith("#"):
                if href[1:] not in c.ids:
                    failures.append(f"[anchor] {rel}:{line}: #{href[1:]} not on this page")
                continue
            if not u.path.startswith("/"):
                failures.append(f"[link] {rel}:{line}: relative link '{href}' "
                                "(use site-absolute paths)")
                continue
            target = url_to_disk(u.path)
            if not os.path.isfile(target):
                failures.append(f"[link] {rel}:{line}: {href} -> missing {os.path.relpath(target, SITE)}")
                continue
            if u.fragment and target in parsed:
                if u.fragment not in parsed[target][0].ids:
                    failures.append(f"[anchor] {rel}:{line}: {href} -> "
                                    f"#{u.fragment} not in {os.path.relpath(target, SITE)}")

        for src, line in c.assets:
            u = urlparse(src)
            if u.scheme in ("http", "https", "data"):
                failures.append(f"[asset] {rel}:{line}: external asset '{src}' "
                                "(site must make no third-party requests)")
                continue
            if not u.path.startswith("/"):
                failures.append(f"[asset] {rel}:{line}: relative src '{src}'")
                continue
            target = os.path.join(SITE, unquote(u.path).lstrip("/"))
            if not os.path.isfile(target):
                failures.append(f"[asset] {rel}:{line}: missing {u.path}")

    # --- pass 3: structure + hygiene ------------------------------------
    for path, (c, raw) in parsed.items():
        rel = os.path.relpath(path, SITE)
        if c.h1 != 1:
            failures.append(f"[struct] {rel}: expected exactly one <h1>, found {c.h1}")
        if not c.title:
            failures.append(f"[struct] {rel}: no <title>")
        for m in ("charset", "viewport", "description"):
            if m not in c.metas and not rel.endswith("404.html"):
                failures.append(f"[struct] {rel}: missing meta {m}")
        if c.imgs_without_alt:
            failures.append(f"[a11y] {rel}: {c.imgs_without_alt} <img> without alt text")
        if not raw.lstrip().lower().startswith("<!doctype html>"):
            failures.append(f"[struct] {rel}: missing <!DOCTYPE html>")
        # placeholders: strip comments first so intentional notes don't trip it
        body = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
        for pat in PLACEHOLDERS:
            if re.search(pat, body):
                failures.append(f"[content] {rel}: placeholder text matching /{pat}/")

    # --- report ----------------------------------------------------------
    print(f"Checked {len(pages)} HTML files under {SITE}")
    for p in sorted(pages):
        print(f"  · {os.path.relpath(p, SITE)}")
    total_links = sum(len(c.links) for c, _ in parsed.values())
    total_assets = sum(len(c.assets) for c, _ in parsed.values())
    print(f"\n{total_links} href(s) and {total_assets} asset reference(s) inspected.")

    if failures:
        print(f"\nFAILED — {len(failures)} problem(s):\n")
        for f in failures:
            print("  ✗", f)
        return 1
    print("\nPASS — every file parses, every internal link and anchor resolves, "
          "no external asset requests, no placeholder text.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
