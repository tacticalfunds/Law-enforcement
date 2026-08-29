# Overbuilt — Roblox game studio website template

A single-file, dependency-free marketing site for a Roblox game studio. Open
`index.html` in a browser or drop it on any static host (GitHub Pages, Netlify,
Cloudflare Pages) — there is no build step.

Every line of studio-defining copy reads `PLACEHOLDER` with a short hint about
what belongs there — studio name, tagline, values, build log, acquisition terms,
process steps, contact details. Search the file for `PLACEHOLDER` to find all of
them; there are 57. The sample game catalogue is left filled in so the grid,
filters, ticker and stat tiles still demonstrate; replace those entries in the
`STUDIO.games` array.

## What's on the page

| Section | What it does |
| --- | --- |
| Hero | Studio pitch, two CTAs, and a live "playing right now" board |
| Ticker | Scrolling marquee of every game and its lifetime visits |
| Stats | Animated counters for visits, concurrents, favourites, group members |
| Our games | Filterable catalogue with generated cover art, per-game metrics |
| Spotlight vote | Community poll with live bars, a reset countdown, one vote per browser |
| Studio | Values and a dated build log |
| Acquisitions | Criteria, deal shape, and a four-step process for sellers |
| Contact | Validated enquiry form with an inquiry-type selector |

## Making it yours

Everything the page renders comes from one object near the top of the `<script>`
block:

```js
const STUDIO = {
  name: "OVERBUILT",
  email: "hello@overbuilt.gg",
  members: 214880,
  links: { group: "…", discord: "…", x: "…", roblox: "…" },
  games: [
    { name:"Rooftop Rivals", initials:"RR", genre:"PvP", status:"Flagship",
      blurb:"…", visits:41204880, live:612, favourites:486210, rating:94,
      c1:"#FF7A3D", c2:"#7A1FA2", pat:"rays" }
  ],
  poll: { "Rooftop Rivals":412, … }
};
```

- **Games** — sample data. Add or remove entries; the grid, genre filters,
  ticker, live board and all four stat tiles recompute from the array.
- **Name and email** — `STUDIO.name` and `STUDIO.email` both read `PLACEHOLDER`.
  The email becomes a working `mailto:` link as soon as it contains an `@`.
- **Cover art** — generated in CSS from `c1`, `c2` and `pat`
  (`rays`, `stripes`, `grid`, `arcs`, `dots`, `bars`). To use real thumbnails,
  replace the `.cover` div in the grid template with an `<img>`.
- **Colours** — one `:root` token block at the top of the stylesheet holds the
  whole palette: near-black ground, red signal, bone type. The page commits to
  this single world rather than following the viewer's light/dark setting, so
  every colour is painted explicitly and nothing is left to `color-scheme`.
  Change `--brand` and `--hot` together to move off red.
- **Type** — Archivo 800 for display, Karla for body, Martian Mono for anything
  numeric. All three come from Google Fonts with real fallback stacks.

## Wiring up the live parts

Two functions are deliberately left as stubs:

- `refreshLive()` currently drifts the demo player counts every 30 seconds.
  Replace its body with a call to the Roblox Games API
  (`games/v1/games?universeIds=…`) — through your own proxy, since Roblox does
  not send CORS headers for browser requests.
- `submitEnquiry(data)` resolves immediately and the form says so. Point it at
  your inbox, a Discord webhook or a form service and it posts for real.

The spotlight vote is stored in `localStorage`, so it is per-browser, not a
shared tally. Swap `paintPolls()` for a fetch against your own counter if you
need real results.

## Accessibility and motion

Keyboard focus is visible throughout, the poll and filters are real buttons with
`aria-pressed`, form errors are announced next to their fields, and everything
animated — counters, reveals, ticker, the halftone background — stops under
`prefers-reduced-motion: reduce`.

Figures shown are sample data. Not affiliated with or endorsed by Roblox
Corporation.
