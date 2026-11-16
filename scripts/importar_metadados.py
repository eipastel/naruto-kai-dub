"""Gera dados/classico.json: título e sinopse em PT-BR de cada episódio do Naruto clássico
(Wikipédia em português, licença CC BY-SA 4.0) e a miniatura oficial do Stremio (Cinemeta).

Uso: python scripts/importar_metadados.py
"""

import json
import re
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
WIKI = ("https://pt.wikipedia.org/w/api.php?action=parse&page=Lista_de_epis%C3%B3dios_de_Naruto"
        "&prop=wikitext&format=json&formatversion=2")
CINEMETA = "https://v3-cinemeta.strem.io/meta/series/tt0409591.json"
# Episódios que não adaptam o mangá: recapitulação (26) e fillers.
FILLERS = {26, 97, *range(101, 107), *range(136, 221)}


def baixar_json(url):
    pedido = urllib.request.Request(url, headers={"User-Agent": "naruto-kai-dub/1.0"})
    with urllib.request.urlopen(pedido, timeout=60) as resposta:
        return json.loads(resposta.read().decode("utf-8", errors="replace"))


def limpar_wiki(texto):
    texto = re.sub(r"<ref[^>]*?/>|<ref.*?</ref>", "", texto, flags=re.S)
    texto = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", texto)  # [[alvo|texto]] -> texto
    texto = re.sub(r"\{\{[^}]*\}\}", "", texto)
    texto = re.sub(r"'{2,}", "", texto)
    texto = re.sub(r"<[^>]+>|}}", "", texto)
    return re.sub(r"\s+", " ", texto).strip()


def main():
    wiki = baixar_json(WIKI)["parse"]["wikitext"]
    episodios = {}
    for bloco in wiki.split("{{Lista de episódio")[1:]:
        campos = dict(re.findall(r"^\|\s*([^=\n]+?)\s*=\s*(.*)$", bloco, flags=re.M))
        numero = re.match(r"\d+", campos.get("NúmeroEpisódio", ""))
        if numero:
            episodios[int(numero[0])] = {
                "titulo": limpar_wiki(campos.get("Título", "")),
                "sinopse": limpar_wiki(campos.get("Sinopse", "")),
            }

    videos = sorted((v for v in baixar_json(CINEMETA)["meta"]["videos"] if v["season"] > 0),
                    key=lambda v: (v["season"], v["episode"]))
    saida = {}
    for n in range(1, 221):
        info = episodios.get(n, {"titulo": "", "sinopse": ""})
        video = videos[n - 1] if n <= len(videos) else {}
        saida[str(n)] = {**info, "filler": n in FILLERS, "miniatura": video.get("thumbnail")}

    faltando = [n for n, e in saida.items() if not e["titulo"]]
    destino = RAIZ / "dados" / "classico.json"
    destino.write_text(json.dumps({
        "fonte": "Títulos e sinopses: Wikipédia em português (CC BY-SA 4.0), "
                 "https://pt.wikipedia.org/wiki/Lista_de_episódios_de_Naruto. Miniaturas: Cinemeta/Stremio.",
        "episodios": saida,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{destino}: {len(saida)} episódios; sem título: {faltando or 'nenhum'}")


if __name__ == "__main__":
    main()
