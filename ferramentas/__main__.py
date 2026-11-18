"""Linha de comando: python -m ferramentas <comando> ...

Comandos (modo clássico: gera o "Kai" a partir do Naruto clássico dublado):
  limpar [episódios]      detecta abertura, encerramento, prévia e recapitulação
  montar [episódios]      gera os MP4 sem esses trechos e registra os links
  legendar [episódios]    transcreve a dublagem (Whisper) e registra a legenda PT-BR
  Episódios: "1-135", "5", "1,2,10-20". Sem argumento = todos os canônicos.

Comandos (modo Kai: usa um arquivo do Naruto Kai como molde):
  novo <episodio>         cria dados/episodios/s01eNNN.json a partir do modelo
  cortes <episodio>       lista os cortes de cena detectados no episódio Kai
  mapear <episodio>       mapeia o Kai nos episódios originais e grava o mapa no JSON
  sincronizar <episodio>  gera o MP4 do Kai com a dublagem PT-BR
  servir                  serve a pasta de saída na rede local (com suporte a avanço/retrocesso)
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import subprocess
from urllib.parse import quote

from . import limpeza, mapeamento, midia, sincronia

RAIZ = Path(__file__).resolve().parent.parent
EPISODIOS = RAIZ / "dados" / "episodios"
CONFIG = RAIZ / "config.local.json"


def chave(episodio, temporada=1):
    return f"s{temporada:02d}e{episodio:03d}"


def carregar_config():
    if not CONFIG.exists():
        sys.exit("config.local.json não encontrado. Copie config.exemplo.json e preencha os caminhos.")
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    cfg["originais_dublados"] = {int(k): Path(v) for k, v in cfg.get("originais_dublados", {}).items()}
    cfg["ajuste_origem_ms"] = {int(k): v for k, v in cfg.get("ajuste_origem_ms", {}).items()}
    return cfg


def ler_episodio(episodio):
    arquivo = EPISODIOS / f"{chave(episodio)}.json"
    if not arquivo.exists():
        sys.exit(f"{arquivo} não existe. Crie com: python -m ferramentas novo {episodio}")
    return arquivo, json.loads(arquivo.read_text(encoding="utf-8"))


def gravar(arquivo, dados):
    arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def caminho_kai(cfg, episodio):
    caminho = cfg.get("kai", {}).get(chave(episodio))
    if not caminho or not Path(caminho).exists():
        sys.exit(f"Arquivo do Kai para {chave(episodio)} não configurado ou inexistente em config.local.json")
    return Path(caminho)


def originais_do_episodio(cfg, dados):
    faltando = [n for n in dados["originais"] if n not in cfg["originais_dublados"]]
    if faltando:
        sys.exit(f"Configure em originais_dublados os episódios originais: {faltando}")
    return {n: cfg["originais_dublados"][n] for n in dados["originais"]}


def cmd_novo(args):
    arquivo = EPISODIOS / f"{chave(args.episodio)}.json"
    if arquivo.exists():
        sys.exit(f"{arquivo} já existe.")
    gravar(arquivo, {
        "temporada": 1, "episodio": args.episodio, "titulo": "", "sinopse": "",
        "capitulos_manga": "", "adicionado_em": "", "miniatura": None,
        "originais": [], "mapa": [], "streams": [],
    })
    print(f"Criado {arquivo}. Preencha título, sinopse e a lista 'originais'.")


def cmd_cortes(args):
    cfg = carregar_config()
    for t in midia.detectar_cortes(caminho_kai(cfg, args.episodio), args.limiar, cfg.get("filtro_kai")):
        print(f"{t:10.3f}")


def cmd_mapear(args):
    cfg = carregar_config()
    arquivo, dados = ler_episodio(args.episodio)
    if dados["mapa"] and not args.forcar:
        sys.exit("Este episódio já tem mapa (talvez com ajustes manuais). Use --forcar para refazer.")
    kai = caminho_kai(cfg, args.episodio)
    originais = originais_do_episodio(cfg, dados)
    mapa = mapeamento.mapear(kai, originais, fps=args.fps, limiar_cena=args.limiar,
                             confianca_minima=args.confianca,
                             filtro_kai=cfg.get("filtro_kai"), filtro_original=cfg.get("filtro_original"))
    if not args.sem_audio and midia.sondar(kai)["tem_audio"]:
        print("Refinando encaixe pelo áudio ...")
        mapeamento.refinar_por_audio(mapa, kai, originais)
    dados["mapa"] = mapa
    gravar(arquivo, dados)
    print(f"\n{'Kai':>19}  {'origem':>6}  {'início no original':>18}  confiança")
    for s in mapa:
        origem = s["origem"] if s["origem"] is not None else "—"
        ini = f"{s['origem_inicio']:.3f}" if s["origem_inicio"] is not None else f"(preencher: {s['preencher']})"
        alerta = "  <- revisar" if s["origem"] is not None and s["confianca"] < 0.8 else ""
        print(f"{s['kai_inicio']:8.3f}–{s['kai_fim']:8.3f}  {origem:>6}  {ini:>18}  {s['confianca']:.2f}{alerta}")
    print(f"\nMapa gravado em {arquivo}")


def cmd_sincronizar(args):
    cfg = carregar_config()
    _, dados = ler_episodio(args.episodio)
    kai = caminho_kai(cfg, args.episodio)
    pasta = Path(cfg.get("pasta_saida", RAIZ / "saida"))
    pasta.mkdir(parents=True, exist_ok=True)
    saida = pasta / f"Naruto Kai Dublado - {chave(args.episodio).upper()}.mp4"
    try:
        sincronia.sincronizar(kai, dados["mapa"], originais_do_episodio(cfg, dados), saida,
                              ajuste_origem_ms=cfg["ajuste_origem_ms"], reencodar=args.reencodar,
                              manter_original=not args.so_dublado,
                              titulo=f"Naruto Kai Dublado {chave(args.episodio).upper()} - {dados['titulo']}")
    except ValueError as erro:
        sys.exit(str(erro))
    print(f"\nPronto: {saida}")


def faixa(texto, permitidos):
    """'1-5,8' -> [1, 2, 3, 4, 5, 8], só com os episódios permitidos."""
    if not texto:
        return sorted(permitidos)
    numeros = set()
    for parte in texto.split(","):
        ini, _, fim = parte.partition("-")
        numeros.update(range(int(ini), int(fim or ini) + 1))
    return sorted(numeros & set(permitidos))


def classico():
    cfg = carregar_config()
    info = cfg.get("classico") or sys.exit("Configure 'classico' (pasta e arquivo) no config.local.json")
    meta = json.loads((RAIZ / "dados" / "classico.json").read_text(encoding="utf-8"))["episodios"]
    arquivo = lambda n: Path(info["pasta"]) / info["arquivo"].format(n=n)  # noqa: E731
    canonicos = [int(n) for n, e in meta.items() if not e["filler"]]
    textos = json.loads((RAIZ / "dados" / "textos.json").read_text(encoding="utf-8"))["episodios"]
    for n, t in textos.items():  # títulos e sinopses próprios, sem spoiler
        meta[n] = {**meta[n], **t}
    return cfg, meta, arquivo, canonicos


def cmd_limpar(args):
    cfg, meta, arquivo, canonicos = classico()
    cache = Path(cfg.get("pasta_saida", RAIZ / "saida")) / ".impressoes"
    impressao = lambda n: limpeza.impressoes(arquivo(n), cache) if arquivo(n).exists() else None  # noqa: E731
    for n in faixa(args.episodios, canonicos):
        if not arquivo(n).exists():
            print(f"E{n:03d}: arquivo não encontrado, pulando")
            continue
        destino = EPISODIOS / f"{chave(n)}.json"
        dados = json.loads(destino.read_text(encoding="utf-8")) if destino.exists() else {}
        if dados.get("revisado") and not args.forcar:
            print(f"E{n:03d}: revisado à mão, mantido (use --forcar para refazer)")
            continue
        vizinhos = [m for m in (n - 5, n - 3, n - 2, n + 2, n + 3, n + 5) if m >= 1 and arquivo(m).exists()]
        removidos = limpeza.detectar(impressao(n), [impressao(m) for m in vizinhos],
                                     [m < n for m in vizinhos], impressao(n - 1) if n > 1 else None)
        duracao = midia.sondar(arquivo(n))["duracao"]
        dados = {
            "temporada": 1, "episodio": n, "original": n,
            "titulo": meta[str(n)]["titulo"], "sinopse": meta[str(n)]["sinopse"],
            "adicionado_em": dados.get("adicionado_em") or date.today().isoformat(),
            "miniatura": meta[str(n)]["miniatura"],
            "duracao_original": round(duracao, 2),
            "revisado": False,
            "removidos": removidos,
            "streams": dados.get("streams", []),
        }
        gravar(destino, dados)
        fica = sum(b - a for a, b in limpeza.manter(removidos, duracao))
        print(f"E{n:03d}: {fica / 60:4.1f} de {duracao / 60:4.1f} min | "
              + ", ".join(f"{r['motivo']} {r['inicio']:.0f}-{r['fim']:.0f}s" for r in removidos))


def cmd_montar(args):
    cfg, meta, arquivo, canonicos = classico()
    pasta = Path(cfg.get("pasta_saida", RAIZ / "saida"))
    pasta.mkdir(parents=True, exist_ok=True)
    for n in faixa(args.episodios, canonicos):
        destino = EPISODIOS / f"{chave(n)}.json"
        if not destino.exists():
            print(f"E{n:03d}: rode 'limpar' antes")
            continue
        dados = json.loads(destino.read_text(encoding="utf-8"))
        nome = f"Naruto Kai Dublado - E{n:03d}.mp4"
        saida = pasta / nome
        if saida.exists() and not args.forcar:
            print(f"E{n:03d}: já existe, pulando")
        else:
            print(f"E{n:03d}: montando {nome} ...")
            temporario = saida.with_name(saida.stem + ".parcial.mp4")
            subprocess.run(limpeza.comando_montagem(arquivo(n), dados["removidos"], temporario,
                                                    cfg.get("codificador", "h264_nvenc"),
                                                    f"Naruto Kai Dublado E{n:03d} - {dados['titulo']}"), check=True)
            temporario.replace(saida)
        if cfg.get("url_streams"):
            # mantém o resto do stream (ex.: legendas) e só atualiza o link
            dados["streams"] = [{**(dados.get("streams") or [{}])[0], "url": f"{cfg['url_streams'].rstrip('/')}/{quote(nome)}"}]
            gravar(destino, dados)


def tempo_srt(segundos):
    """75.5 -> '00:01:15,500'"""
    ms = round(segundos * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


# Nomes que a transcrição costuma errar; servem de dica para o modelo.
VOCABULARIO = "Naruto Uzumaki, Sasuke Uchiha, Sakura Haruno, Kakashi, Iruka, Konoha, Hokage, ninja, jutsu, chakra, Sharingan."


def cmd_legendar(args):
    import importlib.util
    import os
    from faster_whisper import WhisperModel  # pip install faster-whisper
    # No Windows as DLLs CUDA do pip (nvidia-cublas-cu12, nvidia-cudnn-cu12) não ficam no PATH.
    pacote = importlib.util.find_spec("nvidia")
    for raiz in (pacote.submodule_search_locations if pacote else []):
        for bin_ in Path(raiz).glob("*/bin"):
            os.environ["PATH"] = f"{bin_}{os.pathsep}{os.environ['PATH']}"
    cfg, _, _, canonicos = classico()
    pasta = Path(cfg.get("pasta_saida", RAIZ / "saida"))
    modelo = WhisperModel(args.modelo, device=args.dispositivo)
    for n in faixa(args.episodios, canonicos):
        video = pasta / f"Naruto Kai Dublado - E{n:03d}.mp4"
        destino = EPISODIOS / f"{chave(n)}.json"
        if not video.exists() or not destino.exists():
            print(f"E{n:03d}: rode 'montar' antes")
            continue
        legenda = video.with_suffix(".srt")
        if legenda.exists() and not args.forcar:
            print(f"E{n:03d}: legenda já existe, mantida (use --forcar para refazer)")
        else:
            print(f"E{n:03d}: transcrevendo ...", flush=True)
            trechos, _ = modelo.transcribe(str(video), language="pt", vad_filter=True, initial_prompt=VOCABULARIO)
            legenda.write_text("".join(f"{i}\n{tempo_srt(t.start)} --> {tempo_srt(t.end)}\n{t.text.strip()}\n\n"
                                       for i, t in enumerate(trechos, 1)), encoding="utf-8")
        dados = json.loads(destino.read_text(encoding="utf-8"))
        if cfg.get("url_streams") and dados.get("streams"):
            dados["streams"][0]["subtitles"] = [{"id": "pt-br", "lang": "por",
                                                 "url": f"{cfg['url_streams'].rstrip('/')}/{quote(legenda.name)}"}]
            gravar(destino, dados)


def cmd_servir(args):
    from .servidor import servir
    cfg = carregar_config()
    servir(Path(args.pasta or cfg.get("pasta_saida", RAIZ / "saida")), args.porta, https=not args.http)


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m ferramentas", description="Ferramentas do Naruto Kai Dublado")
    sub = p.add_subparsers(dest="comando", required=True)

    s = sub.add_parser("limpar", help="detecta abertura, encerramento, prévia e recapitulação")
    s.add_argument("episodios", nargs="?", help='ex.: "1-135" (padrão: todos os canônicos)')
    s.add_argument("--forcar", action="store_true", help="refaz também os episódios revisados à mão")
    s.set_defaults(func=cmd_limpar)

    s = sub.add_parser("montar", help="gera os MP4 limpos e registra os links")
    s.add_argument("episodios", nargs="?", help='ex.: "1-135" (padrão: todos os canônicos)')
    s.add_argument("--forcar", action="store_true", help="refaz MP4 que já existem")
    s.set_defaults(func=cmd_montar)

    s = sub.add_parser("legendar", help="transcreve a dublagem e registra a legenda PT-BR")
    s.add_argument("episodios", nargs="?", help='ex.: "1-10" (padrão: todos os canônicos)')
    s.add_argument("--modelo", default="large-v3", help="modelo do Whisper (padrão large-v3)")
    s.add_argument("--dispositivo", default="cuda", help="cuda (placa NVIDIA) ou cpu")
    s.add_argument("--forcar", action="store_true", help="refaz legendas que já existem (apaga ajustes manuais)")
    s.set_defaults(func=cmd_legendar)

    s = sub.add_parser("novo", help="cria o JSON de um novo episódio")
    s.add_argument("episodio", type=int)
    s.set_defaults(func=cmd_novo)

    s = sub.add_parser("cortes", help="lista os cortes de cena do episódio Kai")
    s.add_argument("episodio", type=int)
    s.add_argument("--limiar", type=float, default=0.35, help="sensibilidade (0–1, menor = mais cortes)")
    s.set_defaults(func=cmd_cortes)

    s = sub.add_parser("mapear", help="mapeia o Kai nos episódios originais")
    s.add_argument("episodio", type=int)
    s.add_argument("--fps", type=float, default=5, help="quadros por segundo analisados (padrão 5)")
    s.add_argument("--limiar", type=float, default=0.35, help="sensibilidade dos cortes de cena")
    s.add_argument("--confianca", type=float, default=0.6, help="correlação mínima para aceitar um encaixe")
    s.add_argument("--sem-audio", action="store_true", help="não refinar o encaixe pelo áudio")
    s.add_argument("--forcar", action="store_true", help="sobrescreve um mapa existente")
    s.set_defaults(func=cmd_mapear)

    s = sub.add_parser("sincronizar", help="gera o MP4 dublado")
    s.add_argument("episodio", type=int)
    s.add_argument("--reencodar", action=argparse.BooleanOptionalAction, default=None,
                   help="força (ou impede) a recodificação do vídeo para H.264")
    s.add_argument("--so-dublado", action="store_true", help="não inclui o áudio original como 2ª faixa")
    s.set_defaults(func=cmd_sincronizar)

    s = sub.add_parser("servir", help="serve os MP4 na rede local para a TV")
    s.add_argument("--pasta")
    s.add_argument("--porta", type=int, default=8642)
    s.add_argument("--http", action="store_true", help="sem HTTPS (o Stremio web e o das TVs não tocam)")
    s.set_defaults(func=cmd_servir)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
