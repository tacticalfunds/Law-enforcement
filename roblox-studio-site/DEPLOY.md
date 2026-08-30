# Deploying to Railway

The site is one HTML file. Railway is not a static host — it runs containers and
expects a process listening on `$PORT` — so `server.js` hands the file out.
It has no dependencies, so there is nothing to install and nothing to break.

## One-time setup

1. **railway.app → New Project → Deploy from GitHub repo** and pick
   `tacticalfunds/law-enforcement`.

2. **Set the branch.** This is the one that matters. Settings → Source → Branch
   → `claude/roblox-studio-website-oxu45k`.

   The repository's default branch is `claude/plate-reader-code-3lwh5j`, which
   contains no website at all. Left alone, Railway builds that and fails with
   "Railpack could not determine how to build the app", listing only
   `plate-reader/` as the app contents.

3. **Root directory is optional.** The root `package.json` on the site branch
   starts the server for you. Setting Settings → Source → Root Directory to
   `roblox-studio-site` also works if you prefer the service scoped to the site.

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

- **"Railpack could not determine how to build the app"**, with `plate-reader/`
  listed as the app contents — Railway is on the default branch. See step 2.
- **Deploy crashes immediately** — check the deploy logs for the line
  `Serving … on port …`. If it is missing, the container never reached
  `server.js`; if it is there, the failure is downstream, usually the domain not
  being generated yet.

## Other hosts

Nothing here is Railway-specific except this document. `index.html` is a
complete site on its own — Netlify, Cloudflare Pages, GitHub Pages and any
static host will serve it directly, and there `server.js` and `package.json` are
simply unused.
