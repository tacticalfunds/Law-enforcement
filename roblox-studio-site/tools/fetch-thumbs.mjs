#!/usr/bin/env node
/*
  Pulls real thumbnails and live stats for each game straight from Roblox,
  then writes the thumbnails into index.html as data URIs.

  Data URIs rather than links: the page is served as a single file and is
  also published as an artifact, where external images are blocked and a
  linked thumbnail would silently fail to load.

    node tools/fetch-thumbs.mjs            # fetch, report, patch index.html
    node tools/fetch-thumbs.mjs --dry-run  # fetch and report, touch nothing

  Node 18+ (uses built-in fetch). No dependencies.
*/
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const INDEX = path.join(HERE, "..", "index.html");
const DRY = process.argv.includes("--dry-run");

/* key => place id. The key is what index.html references as THUMBS.<key>. */
const GAMES = {
  punch:   "130373433210095",   // 1 Punch to Escape
  boxing:  "128363930903729",   // Boxing Club
  warrior: "135599054283342",   // +1 Warrior Evolution
  keycaps: "115018712071096",   // Keycaps
  paint:    "78724049937437",   // Paint And SEEK!
  monkeys:  "80711300301173",   // Monkeys VS Walls
  glider:  "124036223378608"    // Fly a Glider
};

const api = async (url) => {
  const res = await fetch(url, { headers: { accept: "application/json" } });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${url}`);
  return res.json();
};

/* place id -> universe id, one call each; Roblox has no batch route for this */
const universeIds = {};
for (const [key, placeId] of Object.entries(GAMES)) {
  const { universeId } = await api(`https://apis.roblox.com/universes/v1/places/${placeId}/universe`);
  universeIds[key] = universeId;
  process.stderr.write(`resolved ${key} -> universe ${universeId}\n`);
}

const ids = Object.values(universeIds).join(",");
const [details, thumbs] = await Promise.all([
  api(`https://games.roblox.com/v1/games?universeIds=${ids}`),
  api(`https://thumbnails.roblox.com/v1/games/multiget/thumbnails?universeIds=${ids}&size=768x432&format=Png&isCircular=false`)
]);

const byUniverse = new Map(details.data.map(d => [d.id, d]));
const thumbByUniverse = new Map(thumbs.data.map(t => [t.universeId, t.thumbnails?.[0]?.imageUrl]));

const entries = [];
for (const [key, universeId] of Object.entries(universeIds)) {
  const d = byUniverse.get(universeId);
  const url = thumbByUniverse.get(universeId);
  if (!url) { process.stderr.write(`no thumbnail for ${key}, skipping\n`); continue; }

  const img = await fetch(url);
  const buf = Buffer.from(await img.arrayBuffer());
  const mime = img.headers.get("content-type") || "image/png";
  entries.push({
    key,
    placeId: GAMES[key],
    dataUri: `data:${mime};base64,${buf.toString("base64")}`,
    kb: Math.round(buf.length / 1024),
    name: d?.name,
    creator: d?.creator?.name,
    visits: d?.visits,
    playing: d?.playing,
    maxPlayers: d?.maxPlayers
  });
  process.stderr.write(`fetched ${key} thumbnail (${Math.round(buf.length / 1024)} KB)\n`);
}

/* the numbers, so the catalogue in index.html can be brought up to date */
console.log("\nCurrent figures from Roblox:\n");
for (const e of entries) {
  console.log(`  ${e.key.padEnd(8)} ${String(e.name ?? "?").padEnd(28)} ` +
              `visits ${String(e.visits ?? "?").padStart(10)}  ` +
              `playing ${String(e.playing ?? "?").padStart(5)}  ` +
              `cap ${String(e.maxPlayers ?? "?").padStart(3)}  by ${e.creator ?? "?"}`);
}
const total = Math.round(entries.reduce((a, e) => a + e.kb, 0));
console.log(`\n${entries.length} thumbnails, ${total} KB before base64 (~${Math.round(total * 1.34)} KB inlined).`);

if (DRY) { console.log("\n--dry-run: index.html not touched."); process.exit(0); }

/* replace the THUMBS object in place; it is delimited by its own braces */
const html = await fs.readFile(INDEX, "utf8");
const open = html.indexOf("const THUMBS = {");
if (open === -1) throw new Error("could not find `const THUMBS = {` in index.html");
const close = html.indexOf("\n};", open);
if (close === -1) throw new Error("could not find the end of the THUMBS object");

const block = "const THUMBS = {\n" +
  entries.map(e => `  ${e.key}: "${e.dataUri}"`).join(",\n") +
  "\n}";

await fs.writeFile(INDEX, html.slice(0, open) + block + html.slice(close + 2), "utf8");
console.log(`\nWrote ${entries.length} thumbnails into index.html.`);
console.log("Give each game an `img: THUMBS.<key>` in the STUDIO.games array to show it.");
