/* Static file server for Railway.
   Zero dependencies on purpose: Nixpacks detects package.json, installs
   nothing, and runs `npm start`. Railway sets PORT; binding 0.0.0.0 is
   what makes the service reachable from outside the container. */
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");

const ROOT = __dirname;
const PORT = process.env.PORT || 3000;

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css":  "text/css; charset=utf-8",
  ".js":   "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg":  "image/svg+xml",
  ".png":  "image/png",
  ".jpg":  "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".ico":  "image/x-icon",
  ".woff2":"font/woff2",
  ".txt":  "text/plain; charset=utf-8",
  ".md":   "text/markdown; charset=utf-8"
};

const send = (res, code, type, body) => {
  res.writeHead(code, { "content-type": type, "x-content-type-options": "nosniff" });
  res.end(body);
};

http.createServer((req, res) => {
  if (req.method !== "GET" && req.method !== "HEAD") {
    return send(res, 405, TYPES[".txt"], "Method not allowed");
  }

  let rel = decodeURIComponent(new URL(req.url, "http://localhost").pathname);
  if (rel.endsWith("/")) rel += "index.html";

  const file = path.join(ROOT, rel);
  const inside = path.relative(ROOT, file);
  if (inside.startsWith("..") || path.isAbsolute(inside)) {
    return send(res, 403, TYPES[".txt"], "Forbidden");
  }

  fs.readFile(file, (err, buf) => {
    if (err) {
      /* one page, so anything unrecognised still lands on the site */
      return fs.readFile(path.join(ROOT, "index.html"), (e, home) =>
        e ? send(res, 404, TYPES[".txt"], "Not found")
          : send(res, 404, TYPES[".html"], home));
    }
    const type = TYPES[path.extname(file).toLowerCase()] || "application/octet-stream";
    res.writeHead(200, {
      "content-type": type,
      "x-content-type-options": "nosniff",
      /* the page is one file and changes on every deploy, so revalidate it;
         anything else can sit in cache */
      "cache-control": type.startsWith("text/html")
        ? "no-cache"
        : "public, max-age=86400"
    });
    res.end(req.method === "HEAD" ? undefined : buf);
  });
}).listen(PORT, "0.0.0.0", () => console.log(`Serving ${ROOT} on port ${PORT}`));
