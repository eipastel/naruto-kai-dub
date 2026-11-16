// Gera e serve o complemento em http://127.0.0.1:7000 para testar no Stremio do computador
// antes de publicar. Instale no Stremio colando http://127.0.0.1:7000/manifest.json
import { execFileSync } from "node:child_process";
import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const PORTA = Number(process.env.PORTA || 7000);
const RAIZ = fileURLToPath(new URL("..", import.meta.url));
const DIST = join(RAIZ, "dist");
const TIPOS = { ".json": "application/json; charset=utf-8", ".html": "text/html; charset=utf-8", ".png": "image/png" };

execFileSync(process.execPath, [join(RAIZ, "scripts/build.mjs")], {
  stdio: "inherit",
  env: { ...process.env, NKDUB_URL_BASE: `http://127.0.0.1:${PORTA}` },
});

createServer((req, res) => {
  let caminho = normalize(join(DIST, decodeURIComponent(new URL(req.url, "http://x").pathname)));
  if (caminho.endsWith("\\") || caminho.endsWith("/")) caminho = join(caminho, "index.html");
  res.setHeader("Access-Control-Allow-Origin", "*");
  if (!caminho.startsWith(DIST) || !existsSync(caminho) || !statSync(caminho).isFile()) {
    res.writeHead(404, { "Content-Type": "application/json" }).end('{"erro":"não encontrado"}');
    return;
  }
  res.writeHead(200, { "Content-Type": TIPOS[extname(caminho)] || "application/octet-stream" });
  createReadStream(caminho).pipe(res);
}).listen(PORTA, () => console.log(`Complemento local: http://127.0.0.1:${PORTA}/manifest.json`));
