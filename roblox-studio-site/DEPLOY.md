# Deploying to Railway

The site is one HTML file. Railway is not a static host — it runs containers and
expects a process listening on `$PORT` — so `server.js` hands the file out.
It has no dependencies, so there is nothing to install and nothing to break.

## One-time setup

1. **railway.app → New Project → Deploy from GitHub repo** and pick
   `tacticalfunds/law-enforcement`.

2. **Set the root directory.** This is the step people miss. The repository has
   other projects in it, so without this Railway tries to build the wrong thing.

   Service → **Settings → Source → Root Directory** → `roblox-studio-site`

3. **Set the branch.** Settings → Source → Branch. The site currently lives on
   `claude/roblox-studio-website-oxu45k`. Point Railway at that branch, or merge
   it into your default branch and point at that instead.

4. **Generate a domain.** Settings → Networking → **Generate Domain**. You get a
   `*.up.railway.app` URL. Railway detects the listening port on its own; you do
   not need to set `PORT` yourself.

That is the whole setup. No environment variables, no build command, no start
command — Nixpacks sees `package.json`, installs nothing, and runs `npm start`.

## Your own domain

Settings → Networking → **Custom Domain** → enter it. Railway shows a CNAME
target; add that record at your registrar and wait for it to verify. HTTPS is
issued automatically once DNS resolves.

## Deploying changes

Push to the branch Railway is watching and it redeploys. `index.html` is served
with `cache-control: no-cache`, so browsers revalidate it every load and your
changes appear immediately rather than after a cache expiry.

## Checking it locally first

```
cd roblox-studio-site
npm start
```

Then open http://localhost:3000. Same code path Railway runs.

## If a deploy fails

- **Build succeeds, page 404s** — the root directory is not set. See step 2.
- **"No start command found"** — Railway is building the repository root, not
  `roblox-studio-site`. Same fix.
- **Deploy crashes immediately** — check the deploy logs for the line
  `Serving … on port …`. If it is missing, the container never reached
  `server.js`; if it is there, the failure is downstream, usually the domain not
  being generated yet.

## Other hosts

Nothing here is Railway-specific except this document. `index.html` is a
complete site on its own — Netlify, Cloudflare Pages, GitHub Pages and any
static host will serve it directly, and there `server.js` and `package.json` are
simply unused.
