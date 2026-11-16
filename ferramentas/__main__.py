"""Linha de comando: python -m ferramentas <comando> ...

Comandos:
  novo <episodio>         cria dados/episodios/s01eNNN.json a partir do modelo
  cortes <episodio>       lista os cortes de cena detectados no episódio Kai
  mapear <episodio>       mapeia o Kai nos episódios originais e grava o mapa no JSON
  sincronizar <episodio>  gera o MP4 do Kai com a dublagem PT-BR
  servir                  serve a pasta de saída na rede local (com suporte a avanço/retrocesso)
"""

import argparse
import json
import sys
from pathlib import Path

from . import mapeamento, midia, sincronia

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


def cmd_servir(args):
    from .servidor import servir
    cfg = carregar_config()
    servir(Path(args.pasta or cfg.get("pasta_saida", RAIZ / "saida")), args.porta)


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m ferramentas", description="Ferramentas do Naruto Kai Dublado")
    sub = p.add_subparsers(dest="comando", required=True)

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
    s.set_defaults(func=cmd_servir)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
