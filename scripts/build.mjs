// Gera o complemento Stremio estático em dist/ a partir de dados/.
// Uso: node scripts/build.mjs            (valida e gera)
//      node scripts/build.mjs --validar  (só valida)
import { cpSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = fileURLToPath(new URL("..", import.meta.url));
const DIST = join(RAIZ, "dist");
const URL_BASE = (process.env.NKDUB_URL_BASE || "https://eipastel.github.io/naruto-kai-dub").replace(/\/$/, "");
const lerJson = (arquivo) => JSON.parse(readFileSync(join(RAIZ, arquivo), "utf8"));

const pacote = lerJson("package.json");
const serie = lerJson("dados/serie.json");
const arquivos = readdirSync(join(RAIZ, "dados/episodios")).filter((f) => f.endsWith(".json")).sort();
const episodios = arquivos.map((f) => ({ arquivo: f, ...lerJson(`dados/episodios/${f}`) }));

// ---------- validação ----------
const erros = [];
const erro = (onde, msg) => erros.push(`${onde}: ${msg}`);
const texto = (v) => typeof v === "string" && v.trim() !== "";

if (!/^[a-z0-9]+$/.test(serie.id)) erro("serie.json", "id deve ter só letras minúsculas e números");
if (!texto(serie.nome) || !texto(serie.descricao)) erro("serie.json", "nome e descricao são obrigatórios");

const vistos = new Set();
for (const ep of episodios) {
  const onde = ep.arquivo;
  const nomeEsperado = `s${String(ep.temporada).padStart(2, "0")}e${String(ep.episodio).padStart(3, "0")}.json`;
  if (ep.arquivo !== nomeEsperado) erro(onde, `nome do arquivo deveria ser ${nomeEsperado}`);
  if (vistos.has(nomeEsperado)) erro(onde, "episódio duplicado");
  vistos.add(nomeEsperado);
  if (!texto(ep.titulo)) erro(onde, "titulo é obrigatório");
  if (typeof ep.sinopse !== "string") erro(onde, "sinopse deve ser texto");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(ep.adicionado_em ?? "")) erro(onde, "adicionado_em deve ser AAAA-MM-DD");
  if (!Array.isArray(ep.originais) || !ep.originais.every((n) => Number.isInteger(n) && n > 0))
    erro(onde, "originais deve ser uma lista de números de episódio");

  (ep.mapa ?? []).forEach((s, i) => {
    if (!(s.kai_fim > s.kai_inicio)) erro(onde, `mapa[${i}]: kai_fim deve ser maior que kai_inicio`);
    const anterior = ep.mapa[i - 1];
    if (i === 0 && Math.abs(s.kai_inicio) > 0.001) erro(onde, "mapa[0] deve começar em 0");
    if (anterior && Math.abs(s.kai_inicio - anterior.kai_fim) > 0.001) erro(onde, `mapa[${i}]: buraco ou sobreposição`);
    if (s.origem != null && typeof s.origem_inicio !== "number") erro(onde, `mapa[${i}]: falta origem_inicio`);
    if (s.origem != null && !ep.originais.includes(s.origem)) erro(onde, `mapa[${i}]: origem ${s.origem} fora de 'originais'`);
  });

  (ep.streams ?? []).forEach((s, i) => {
    const fontes = ["url", "infoHash", "ytId", "externalUrl"].filter((k) => k in s);
    if (fontes.length !== 1) erro(onde, `streams[${i}]: informe exatamente um entre url, infoHash, ytId, externalUrl`);
    if (s.url && !/^https?:\/\//.test(s.url)) erro(onde, `streams[${i}]: url deve começar com http:// ou https://`);
    if (s.infoHash && !/^[a-f0-9]{40}$/i.test(s.infoHash)) erro(onde, `streams[${i}]: infoHash inválido`);
  });
}

if (erros.length) {
  console.error(`✗ ${erros.length} problema(s) nos dados:\n  - ${erros.join("\n  - ")}`);
  process.exit(1);
}
console.log(`✓ Dados válidos: ${episodios.length} episódio(s).`);
if (process.argv.includes("--validar")) process.exit(0);

// ---------- geração ----------
const arte = (nome) => `${URL_BASE}/assets/${nome}`;
const idVideo = (ep) => `${serie.id}-${ep.temporada}-${ep.episodio}`;
const codigo = (ep) => `T${ep.temporada}E${String(ep.episodio).padStart(2, "0")}`;
const escrever = (caminho, dados) => {
  const destino = join(DIST, caminho);
  mkdirSync(join(destino, ".."), { recursive: true });
  writeFileSync(destino, typeof dados === "string" ? dados : JSON.stringify(dados));
};

rmSync(DIST, { recursive: true, force: true });
mkdirSync(DIST, { recursive: true });
cpSync(join(RAIZ, "assets"), join(DIST, "assets"), { recursive: true });
writeFileSync(join(DIST, ".nojekyll"), "");

const resumo = {
  id: serie.id,
  type: "series",
  name: serie.nome,
  poster: arte("poster.png"),
  posterShape: "poster",
  background: arte("fundo.png"),
  logo: arte("logo.png"),
  description: serie.descricao,
  genres: serie.generos,
  releaseInfo: serie.ano,
};

escrever("manifest.json", {
  id: `com.github.eipastel.${serie.id}`,
  version: pacote.version,
  name: serie.nome,
  description: serie.descricao,
  logo: arte("logo.png"),
  background: arte("fundo.png"),
  resources: ["catalog", "meta", "stream"],
  types: ["series"],
  idPrefixes: [serie.id],
  catalogs: [{ type: "series", id: serie.id, name: serie.nome }],
  behaviorHints: { configurable: false, configurationRequired: false },
});

escrever(`catalog/series/${serie.id}.json`, { metas: [resumo] });

escrever(`meta/series/${serie.id}.json`, {
  meta: {
    ...resumo,
    videos: episodios.map((ep) => ({
      id: idVideo(ep),
      title: `${codigo(ep)} — ${ep.titulo}`,
      season: ep.temporada,
      episode: ep.episodio,
      released: new Date(`${ep.adicionado_em}T12:00:00Z`).toISOString(),
      overview: [ep.sinopse, ep.capitulos_manga && `Capítulos do mangá: ${ep.capitulos_manga}.`].filter(Boolean).join("\n\n"),
      thumbnail: ep.miniatura ? arte(ep.miniatura) : arte("fundo.png"),
    })),
  },
});

for (const ep of episodios) {
  escrever(`stream/series/${idVideo(ep)}.json`, {
    streams: ep.streams.map((s) => ({
      name: "Naruto Kai\nDublado",
      title: `${codigo(ep)} — ${ep.titulo}\n🇧🇷 Português (Brasil)`,
      ...s,
      behaviorHints: { bingeGroup: `${serie.id}-dublado`, ...s.behaviorHints },
    })),
  });
}

const urlManifesto = `${URL_BASE}/manifest.json`;
const lista = episodios
  .map((ep) => `<li><strong>${codigo(ep)}</strong> ${ep.titulo}${ep.streams.length ? "" : ' <span class="pendente">em preparação</span>'}</li>`)
  .join("\n        ");
escrever(
  "index.html",
  readFileSync(join(RAIZ, "site/index.html"), "utf8")
    .replaceAll("{{MANIFESTO}}", urlManifesto)
    .replaceAll("{{STREMIO}}", urlManifesto.replace(/^https?:\/\//, "stremio://"))
    .replaceAll("{{VERSAO}}", pacote.version)
    .replaceAll("{{EPISODIOS}}", lista),
);

console.log(`✓ Complemento gerado em dist/ (manifesto: ${urlManifesto})`);
if (!existsSync(join(DIST, "assets/poster.png"))) console.warn("! assets/poster.png não encontrado");
