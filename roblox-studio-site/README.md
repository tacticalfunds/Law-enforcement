# Red Lab Studios — site

A single-file, dependency-free marketing site for a Roblox game studio. Open
`index.html` in a browser or drop it on any static host (GitHub Pages, Netlify,
Cloudflare Pages) — there is no build step. For Railway, which runs a process
rather than serving files, `server.js` hands the page out; see `DEPLOY.md`.

Every line of studio-defining copy reads `PLACEHOLDER` with a short hint about
what belongs there — studio name, tagline, values, build log, acquisition terms,
process steps, contact details. Search the file for `PLACEHOLDER` to find all of
them; there are 1. The `STUDIO.games` array holds four real games — where a
number has not been supplied yet it is `null`, so the card renders an em dash
and the totals skip it. Nothing on the page is a guess. The grid sorts itself by
lifetime visits, so the section's claim stays true as you add entries.

## What's on the page

| Section | What it does |
| --- | --- |
| Hero | Studio pitch, two CTAs, and a live "playing right now" board |
| Stats | Animated counters for visits, concurrents, experiences live, largest server |
| Our games | Filterable catalogue with generated cover art, per-game metrics |
| Acquisitions | What we look for, and a three-step process for sellers |
| Contact | Validated enquiry form with an inquiry-type selector |

`CONTENT-BRIEF.md` next to this file lists every placeholder as a fill-in
prompt — answer what you can and send it back.

## Making it yours

Everything the page renders comes from one object near the top of the `<script>`
block:

```js
const STUDIO = {
  name: "PLACEHOLDER",
  email: "PLACEHOLDER",
  links: { group: "…", discord: "…", x: "…", roblox: "…" },
  games: [
    { name:"Paint And SEEK!", initials:"PS", genre:"Hide & seek", status:"Live",
      creator:"Blend In Or Die",
      url:"https://www.roblox.com/games/78724049937437/Paint-And-SEEK",
      blurb:"…", visits:104569069, live:281, maxPlayers:14,
      c1:"#160305", c2:"#D3121F", pat:"dots" }
  ],
  poll: { "Paint And SEEK!":0, … }
};
```

- **Games** — add or remove entries; the grid, genre filters, ticker, live
  board and all four stat tiles recompute from the array. The grid uses
  `auto-fit`, so any number of cards fills the row. Set `visits`, `live` or
  `maxPlayers` to `null` until you have the real figure.
- **Name and links** — `STUDIO.name` and `STUDIO.links` drive the wordmark, the
  footer icons and every Discord link on the page.
- **Thumbnails** — give a game an `img` and the card shows that instead of the
  generated art. External images are blocked, so thumbnails are inlined as data
  URIs in the `THUMBS` object above `STUDIO`; export at 768x432 and paste one in.
- **Cover art** — the fallback when a game has no `img`, generated in CSS from
  `c1`, `c2` and `pat` (`rays`, `stripes`, `grid`, `arcs`, `dots`, `bars`).
- **Colours** — one `:root` token block at the top of the stylesheet holds the
  whole palette: near-black ground, red signal, bone type. The page commits to
  this single world rather than following the viewer's light/dark setting, so
  every colour is painted explicitly and nothing is left to `color-scheme`.
  Change `--brand` and `--hot` together to move off red.
- **Type** — Archivo 800 for display, Karla for body, Martian Mono for anything
  numeric. All three come from Google Fonts with real fallback stacks.
- **Holographic layer** — `--holo` is one oil-slick gradient reused everywhere:
  display type, the logo mark, card rims and cover sheens. JS writes the pointer position into `--mx` / `--my`, which
  those gradients read as their background position, so the foil tilts as you
  move across the page; touch devices get a slow drift instead. The ambient
  canvas paints the same spectrum — dot size and hue both track one wave, giving
  a diffraction pattern rather than a flat halftone.

## Wiring up the live parts

Two functions are deliberately left as stubs:

- `refreshLive()` currently drifts the demo player counts every 30 seconds.
  Replace its body with a call to the Roblox Games API
  (`games/v1/games?universeIds=…`) — through your own proxy, since Roblox does
  not send CORS headers for browser requests.
- `submitEnquiry(data)` resolves immediately and the form says so. Point it at
  your inbox, a Discord webhook or a form service and it posts for real.

## Accessibility and motion

Keyboard focus is visible throughout, the genre filters are real buttons with
`aria-pressed`, form errors are announced next to their fields, and everything
animated — counters, reveals, ticker, the halftone background — stops under
`prefers-reduced-motion: reduce`.

Figures shown are sample data. Not affiliated with or endorsed by Roblox
Corporation.
