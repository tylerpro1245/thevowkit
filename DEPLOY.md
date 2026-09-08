# Deploying thevowkit.com to Cloudflare Pages

Static site. No build step, no dependencies, no framework. Cloudflare Pages just copies the
directory to its edge and serves it.

**Repo:** `tylerpro1245/thevowkit` (public) · **Branch:** `main` · **Site root:** repository root
**Current state:** the domain is presently served by **GitHub Pages** (four GitHub `A` records at
Porkbun). Section 4 removes those; do not skip it or the apex will keep resolving to GitHub.

---

## 0. What gets deployed

```
/                                       ← Cloudflare Pages build output directory = repo root
├── index.html
├── mexico-marriage-requirements.html
├── kits.html
├── about.html
├── contact.html
├── 404.html                            ← Pages serves this automatically on unmatched paths
├── sitemap.xml
├── robots.txt
├── favicon.svg
├── CNAME                               ← GitHub Pages artifact; harmless on Cloudflare, see §7
├── 8f3a1c94d2b74e6fa05c17e9b3d84a26.txt ← IndexNow key file, must stay at root
└── assets/
    ├── css/site.css
    └── img/*.png
```

---

## 1. Push the site to GitHub

`gh` is already authenticated as **tylerpro1245** (scopes `repo`, `read:org`), and the repo already
exists with `origin` configured.

```bash
cd /opt/data/venture/site

git add -A
git commit -m "Rebuild site: free Mexico marriage reference as the lead page"
git push origin main
```

Confirm it landed:

```bash
gh repo view tylerpro1245/thevowkit --json pushedAt,defaultBranchRef
gh api repos/tylerpro1245/thevowkit/contents/mexico-marriage-requirements.html --jq .size
```

If `origin` is ever missing:

```bash
gh repo set-default tylerpro1245/thevowkit
git remote add origin https://github.com/tylerpro1245/thevowkit.git
```

---

## 2. Create the Cloudflare Pages project

Cloudflare Pages' Git integration is a **dashboard-only OAuth flow** — the GitHub App that grants
Cloudflare read access to the repo cannot be installed from the API or from `gh`. Do this once, by
hand, in a browser signed into the Cloudflare account that owns (or will own) `thevowkit.com`.

1. Cloudflare dashboard → **Workers & Pages** → **Create** → **Pages** tab → **Connect to Git**.
2. **Connect GitHub**, authorise as `tylerpro1245`, and grant access to **only** the `thevowkit`
   repository (not "All repositories").
3. Pick repository `tylerpro1245/thevowkit` → **Begin setup**.
4. Build settings — this is a plain static site, so all three fields are deliberately empty/none:

   | Field | Value |
   |---|---|
   | Project name | `thevowkit` |
   | Production branch | `main` |
   | Framework preset | **None** |
   | Build command | *(leave empty)* |
   | Build output directory | `/` |
   | Root directory | `/` |
   | Environment variables | none |

5. **Save and Deploy.** First deploy takes well under a minute since nothing is built.
6. Note the assigned preview hostname: **`thevowkit.pages.dev`**. Confirm it works before touching
   DNS:

   ```bash
   curl -sI https://thevowkit.pages.dev/ | head -1
   curl -s https://thevowkit.pages.dev/mexico-marriage-requirements.html | grep -c "Registro Civil"
   ```

Every later `git push origin main` redeploys automatically. Pushes to any other branch produce a
preview deployment at `<hash>.thevowkit.pages.dev` and do not touch production.

---

## 3. Add `thevowkit.com` to Cloudflare as a zone

**This step is not optional, and it is the reason section 4 changes nameservers rather than adding
records.** Cloudflare's own documentation states: *"To deploy your Pages project to a custom apex
domain, that custom domain must be a zone on the Cloudflare account you have created your Pages
project on."* An apex cannot be a CNAME per RFC 1034, and Cloudflare Pages routes by `Host` header —
so pointing an ALIAS at `thevowkit.pages.dev` from a third-party DNS provider yields an error page,
not the site. See section 8 for the only real alternative.

1. Cloudflare dashboard → **Add a domain** → enter `thevowkit.com` → select the **Free** plan.
2. Cloudflare scans the existing Porkbun zone and imports what it finds. **Review the imported
   records now:**
   - **Delete** the four GitHub Pages `A` records at the apex — `185.199.108.153`,
     `185.199.109.153`, `185.199.110.153`, `185.199.111.153`.
   - **Delete** the `www` CNAME pointing to `tylerpro1245.github.io`.
   - **Keep** any MX, TXT (SPF/DKIM/DMARC) or verification records for `hello@thevowkit.com`. If
     mail is broken after cutover, a missing MX or SPF record imported incorrectly is the cause.
3. Cloudflare shows **two assigned nameservers**, unique to this account, of the form
   `<name>.ns.cloudflare.com` (e.g. `dana.ns.cloudflare.com` / `rob.ns.cloudflare.com`). Copy both
   exactly — the names are assigned per-account and are not guessable.

---

## 4. Porkbun: point the nameservers at Cloudflare

This is the only change required at Porkbun for the supported apex path. The A/CNAME records are
created on the **Cloudflare** side once the zone is active.

**Porkbun dashboard:** log in → **Domain Management** → `thevowkit.com` → **NS / Nameservers** (the
"Authoritative Nameservers" panel, not the DNS records editor) → **Edit** → replace **all** existing
entries with exactly the two Cloudflare gave you in §3.3:

| Field | Value |
|---|---|
| Nameserver 1 | `<assigned-name-1>.ns.cloudflare.com` |
| Nameserver 2 | `<assigned-name-2>.ns.cloudflare.com` |

Remove Porkbun's own `curitiba.ns.porkbun.com` / `fortaleza.ns.porkbun.com` / `maceio.ns.porkbun.com`
/ `salvador.ns.porkbun.com` entries. Save.

> **Note on the Porkbun DNS records editor:** once nameservers are delegated to Cloudflare, any
> records still listed in Porkbun's DNS editor are inert. Do not spend time cleaning them; they stop
> being authoritative the moment delegation propagates. The records that matter now live in
> Cloudflare's DNS tab.

**Via the Porkbun API instead of the dashboard** (credentials already on disk at
`/opt/data/venture/.porkbun-api`, same auth pattern as `/opt/data/venture/scripts/dns_pages.py`):

```bash
# Read current nameservers
curl -s -X POST https://api.porkbun.com/api/json/v3/domain/getNs/thevowkit.com \
  -H 'Content-Type: application/json' \
  -d '{"apikey":"'"$PORKBUN_API_KEY"'","secretapikey":"'"$PORKBUN_SECRET_KEY"'"}'

# Replace them (substitute the two names Cloudflare assigned)
curl -s -X POST https://api.porkbun.com/api/json/v3/domain/updateNs/thevowkit.com \
  -H 'Content-Type: application/json' \
  -d '{"apikey":"'"$PORKBUN_API_KEY"'","secretapikey":"'"$PORKBUN_SECRET_KEY"'",
       "ns":["NAME1.ns.cloudflare.com","NAME2.ns.cloudflare.com"]}'
```

Delegation usually completes in minutes; allow up to 24 hours. Cloudflare emails when the zone goes
**Active**. Verify:

```bash
dig +short NS thevowkit.com
```

---

## 5. The exact DNS records for the apex (created in Cloudflare, after the zone is Active)

Cloudflare normally creates these automatically when you attach the custom domain in §6. If it does
not, add them by hand under **Cloudflare → thevowkit.com → DNS → Records**:

| Type | Name | Target | Proxy status | TTL |
|---|---|---|---|---|
| `CNAME` | `@` (renders as `thevowkit.com`) | `thevowkit.pages.dev` | **Proxied** (orange cloud) | Auto |
| `CNAME` | `www` | `thevowkit.pages.dev` | **Proxied** (orange cloud) | Auto |

The apex `CNAME` is legal here only because Cloudflare applies **CNAME flattening** — it answers
external queries for `thevowkit.com` with `A`/`AAAA` records resolved at query time. This is exactly
the capability Porkbun's own DNS cannot provide for a Pages project.

Both records **must be Proxied** (orange cloud). Grey-cloud/DNS-only breaks Pages routing and TLS.

**Then delete anything left over from GitHub Pages** if the §3.2 import brought it across:

- ✗ `A @ 185.199.108.153`
- ✗ `A @ 185.199.109.153`
- ✗ `A @ 185.199.110.153`
- ✗ `A @ 185.199.111.153`
- ✗ `CNAME www tylerpro1245.github.io`

---

## 6. Attach the custom domains to the Pages project

1. **Workers & Pages** → `thevowkit` → **Custom domains** → **Set up a custom domain**.
2. Enter `thevowkit.com` → **Continue** → **Activate domain**. Because the zone is now on this
   account, Cloudflare creates/validates the flattened apex record itself.
3. Repeat for `www.thevowkit.com`.
4. Wait for both to show **Active**. The Universal SSL certificate is issued automatically —
   typically a few minutes, occasionally up to ~15. There is nothing to configure; do not buy a
   certificate.
5. **SSL/TLS** → **Overview** → set encryption mode to **Full (strict)**.
6. **SSL/TLS** → **Edge Certificates** → enable **Always Use HTTPS**.

### Optional: redirect `www` → apex

Pages serves both hostnames identically, which duplicates the site at two addresses. Every
`<link rel="canonical">` on this site points at the apex, so search engines will resolve it
correctly, but a hard redirect is cleaner. **Rules** → **Redirect Rules** → **Create rule**:

- **If** — Hostname *equals* `www.thevowkit.com`
- **Then** — Dynamic redirect, **301**, expression:
  `concat("https://thevowkit.com", http.request.uri.path)`
- Preserve query string: **on**

---

## 7. Verify the cutover

```bash
# Apex resolves to Cloudflare (104.x / 172.6x ranges), not 185.199.x
dig +short thevowkit.com

# Every page returns 200 over HTTPS
for p in / /mexico-marriage-requirements.html /kits.html /about.html /contact.html \
         /sitemap.xml /robots.txt /assets/css/site.css; do
  printf '%s %s\n' "$(curl -sI -o /dev/null -w '%{http_code}' "https://thevowkit.com$p")" "$p"
done

# Served by Cloudflare, not GitHub
curl -sI https://thevowkit.com/ | grep -iE '^(server|cf-ray|content-type)'

# 404 handling
curl -sI -o /dev/null -w '%{http_code}\n' https://thevowkit.com/no-such-page

# www redirects (if the rule in §6 was added)
curl -sI -o /dev/null -w '%{http_code} %{redirect_url}\n' https://www.thevowkit.com/

# IndexNow key file still reachable at root
curl -s https://thevowkit.com/8f3a1c94d2b74e6fa05c17e9b3d84a26.txt
```

**Housekeeping after a successful cutover:**

- The `CNAME` file at the repo root is a GitHub Pages artifact. Cloudflare Pages ignores it, so it is
  safe to leave, but deleting it prevents confusion about which host is authoritative.
- Disable GitHub Pages so the old deployment cannot resurface:
  ```bash
  gh api -X DELETE repos/tylerpro1245/thevowkit/pages
  ```
- Re-submit the sitemap: `https://thevowkit.com/sitemap.xml`, and re-run
  `/opt/data/venture/scripts/indexnow.py` with the five current URLs.

---

## 8. If the nameservers cannot move to Cloudflare

There is no supported way to serve a **Cloudflare Pages apex** from third-party DNS. An `ALIAS`
record at Porkbun pointing to `thevowkit.pages.dev` will resolve, but Pages routes by `Host` header
and will not recognise an apex that is not a zone on the account — the visitor gets a Cloudflare
error page, not the site. Do not ship that.

The only honest fallback keeps Porkbun as DNS and makes **www** canonical:

| Where | Type | Host | Value | TTL |
|---|---|---|---|---|
| Porkbun DNS records | `CNAME` | `www` | `thevowkit.pages.dev` | 600 |
| Porkbun URL Forwarding | 301 permanent | `thevowkit.com` (apex) | `https://www.thevowkit.com` | — |

Then add **only** `www.thevowkit.com` as the Pages custom domain (§6), and update every
`<link rel="canonical">` and every `og:url` in the five HTML files, plus `sitemap.xml`, from
`https://thevowkit.com/…` to `https://www.thevowkit.com/…`. Skipping that last part points search
engines at a URL that only redirects.

Cloudflare's nameservers are free and this fallback costs a redirect hop on every apex visit — take
section 4 unless there is a specific reason not to.

---

## 9. Rollback

Cloudflare Pages keeps every deployment. **Workers & Pages** → `thevowkit` → **Deployments** → pick a
known-good build → **Rollback to this deployment**. Instant, no rebuild.

To abandon Cloudflare entirely and return to GitHub Pages: restore the four GitHub `A` records and
the `www` CNAME at Porkbun (`/opt/data/venture/scripts/dns_pages.py --apply` does exactly this),
point the nameservers back to Porkbun's own, and re-enable Pages in the repo settings.
