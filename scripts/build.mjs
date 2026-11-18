// Gera o complemento Stremio estático em dist/ a partir de dados/.
// Uso: node scripts/build.mjs            (valida e gera)
//      node scripts/build.mjs --validar  (só valida)
import { cpSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = fileURLToPath(new URL("..", import.meta.url));
const DIST = join(RAIZ, "dist");
// Espelho no jsDelivr (certificado Sectigo): é o endereço que funciona nas TVs LG antigas.
const URL_ESPELHO = (process.env.URL_ESPELHO || "https://cdn.jsdelivr.net/gh/eipastel/pastel-provider@addon").replace(/\/$/, "");
const lerJson = (arquivo) => JSON.parse(readFileSync(join(RAIZ, arquivo), "utf8"));

const pacote = lerJson("package.json");
const serie = lerJson("dados/serie.json");
const arquivos = readdirSync(join(RAIZ, "dados/episodios")).filter((f) => f.endsWith(".json")).sort();
// Títulos e sinopses próprios (sem spoiler) têm prioridade sobre os gravados em cada episódio.
const textos = lerJson("dados/textos.json").episodios;
const episodios = arquivos.map((f) => {
  const ep = lerJson(`dados/episodios/${f}`);
  return { arquivo: f, ...ep, ...textos[String(ep.original ?? ep.episodio)] };
});

// ---------- validação ----------
const erros = [];
const erro = (onde, msg) => erros.push(`${onde}: ${msg}`);
const texto = (v) => typeof v === "string" && v.trim() !== "";

if (!/^[a-z0-9]+$/.test(serie.id)) erro("serie.json", "id deve ter só letras minúsculas e números");
if (!texto(serie.nome) || !texto(serie.descricao)) erro("serie.json", "nome e descricao são obrigatórios");
for (const k of ["poster", "fundo"]) if (!texto(serie.arte?.[k])) erro("serie.json", `arte.${k} é obrigatório`);
for (const ep of episodios) if (!texto(serie.temporadas?.[ep.temporada]?.nome)) erro(ep.arquivo, `temporada ${ep.temporada} sem nome em serie.json`);

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
  if ("mapa" in ep) {
    // modo Kai: o episódio é montado sobre um arquivo do Naruto Kai
    if (!Array.isArray(ep.originais) || !ep.originais.every((n) => Number.isInteger(n) && n > 0))
      erro(onde, "originais deve ser uma lista de números de episódio");
    ep.mapa.forEach((s, i) => {
      if (!(s.kai_fim > s.kai_inicio)) erro(onde, `mapa[${i}]: kai_fim deve ser maior que kai_inicio`);
      const anterior = ep.mapa[i - 1];
      if (i === 0 && Math.abs(s.kai_inicio) > 0.001) erro(onde, "mapa[0] deve começar em 0");
      if (anterior && Math.abs(s.kai_inicio - anterior.kai_fim) > 0.001) erro(onde, `mapa[${i}]: buraco ou sobreposição`);
      if (s.origem != null && typeof s.origem_inicio !== "number") erro(onde, `mapa[${i}]: falta origem_inicio`);
      if (s.origem != null && !ep.originais.includes(s.origem)) erro(onde, `mapa[${i}]: origem ${s.origem} fora de 'originais'`);
    });
  } else {
    // modo clássico: o episódio é o original sem abertura, encerramento, prévia e recapitulação
    if (!Number.isInteger(ep.original) || ep.original < 1) erro(onde, "original deve ser o número do episódio clássico");
    if (!Array.isArray(ep.removidos)) erro(onde, "removidos deve ser uma lista");
    (ep.removidos ?? []).forEach((r, i) => {
      if (!(r.fim > r.inicio) || r.inicio < 0) erro(onde, `removidos[${i}]: fim deve ser maior que inicio`);
      if (i && r.inicio < ep.removidos[i - 1].fim) erro(onde, `removidos[${i}]: sobrepõe o anterior ou fora de ordem`);
      if (ep.duracao_original && r.fim > ep.duracao_original + 0.5) erro(onde, `removidos[${i}]: passa do fim do vídeo`);
    });
  }

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
const idVideo = (ep) => `${serie.id}-${ep.temporada}-${ep.episodio}`;
const codigo = (ep) => `E${String(ep.episodio).padStart(3, "0")}`;
const escrever = (caminho, dados) => {
  const destino = join(DIST, caminho);
  mkdirSync(join(destino, ".."), { recursive: true });
  writeFileSync(destino, typeof dados === "string" ? dados : JSON.stringify(dados));
};

rmSync(DIST, { recursive: true, force: true });
mkdirSync(DIST, { recursive: true });
writeFileSync(join(DIST, ".nojekyll"), "");

// Arte: caminhos relativos vêm de site/ e são servidos pelo espelho; URLs completas passam direto.
cpSync(join(RAIZ, "site/arte"), join(DIST, "arte"), { recursive: true });
const arte = (v) => (v && !/^https?:\/\//.test(v) ? `${URL_ESPELHO}/${v}` : v);
const [poster, fundo, logo] = ["poster", "fundo", "logo"].map((k) => arte(serie.arte[k]));
const temporada = (ep) => serie.temporadas[ep.temporada];
const arcoDe = (ep) => {
  const n = ep.original ?? ep.episodio;
  return temporada(ep).arcos?.find((a) => n >= a.de && n <= a.ate)?.nome;
};
const minutos = (ep) => {
  if (!ep.duracao_original) return null;
  const removido = (ep.removidos ?? []).reduce((t, r) => t + (r.fim - r.inicio), 0);
  return Math.round((ep.duracao_original - removido) / 60);
};

const resumo = {
  id: serie.id,
  type: "series",
  name: serie.nome,
  poster,
  posterShape: "poster",
  background: fundo,
  logo,
  description: serie.descricao,
  genres: serie.generos,
  releaseInfo: serie.ano,
};

escrever("manifest.json", {
  id: `com.github.eipastel.${serie.id}`,
  version: pacote.version,
  name: serie.nome,
  description: serie.descricao,
  logo,
  background: fundo,
  resources: ["catalog", "meta", "stream", "subtitles"],
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
      title: `${temporada(ep).nome} · ${codigo(ep)} — ${ep.titulo}`,
      season: ep.temporada,
      episode: ep.episodio,
      released: new Date(`${ep.adicionado_em}T12:00:00Z`).toISOString(),
      overview: [
        `Temporada ${ep.temporada}: ${temporada(ep).nome}.${arcoDe(ep) ? ` Arco: ${arcoDe(ep)}.` : ""}`,
        ep.sinopse,
        ep.capitulos_manga && `Capítulos do mangá: ${ep.capitulos_manga}.`,
        minutos(ep) && `${minutos(ep)} min, sem abertura, encerramento e recapitulação.`,
      ].filter(Boolean).join("\n\n"),
      thumbnail: ep.miniatura || fundo,
    })),
  },
});

for (const ep of episodios) {
  escrever(`stream/series/${idVideo(ep)}.json`, {
    streams: ep.streams.map((s) => ({
      name: "Pastel\nProvider",
      ...s,
      title: `${temporada(ep).nome} · ${codigo(ep)} — ${ep.titulo}\n🇧🇷 Dublado${minutos(ep) ? ` · ${minutos(ep)} min` : ""}`,
      behaviorHints: { bingeGroup: `${serie.id}-dublado`, ...s.behaviorHints },
    })),
  });
  // As mesmas legendas também como recurso "subtitles": o Stremio das TVs ignora as que vêm dentro do stream.
  escrever(`subtitles/series/${idVideo(ep)}.json`, { subtitles: ep.streams.flatMap((s) => s.subtitles ?? []) });
}

const urlManifesto = `${URL_ESPELHO}/manifest.json`;
const escapar = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const cartoes = episodios
  .map((ep) => `<li class="ep${ep.streams.length ? "" : " pendente"}">
          <img src="${escapar(ep.miniatura || fundo)}" alt="" loading="lazy">
          <span class="num">${codigo(ep)}</span>
          <strong>${escapar(ep.titulo)}</strong>
          <small>${escapar(arcoDe(ep) ?? temporada(ep).nome)}${minutos(ep) ? ` · ${minutos(ep)} min` : ""}</small>
        </li>`)
  .join("\n        ");
const disponiveis = episodios.filter((ep) => ep.streams.length).length;
escrever(
  "index.html",
  readFileSync(join(RAIZ, "site/index.html"), "utf8")
    .replaceAll("{{MANIFESTO}}", urlManifesto)
    .replaceAll("{{STREMIO}}", urlManifesto.replace(/^https?:\/\//, "stremio://"))
    .replaceAll("{{VERSAO}}", pacote.version)
    .replaceAll("{{EPISODIOS}}", cartoes)
    .replaceAll("{{TOTAL}}", String(episodios.length))
    .replaceAll("{{DISPONIVEIS}}", String(disponiveis))
    .replaceAll("{{POSTER}}", poster)
    .replaceAll("{{FUNDO}}", fundo)
    .replaceAll("{{DESCRICAO}}", escapar(serie.descricao.split("\n")[0])),
);

console.log(`✓ Complemento gerado em dist/ (manifesto: ${urlManifesto}; ${disponiveis}/${episodios.length} episódios com vídeo)`);
