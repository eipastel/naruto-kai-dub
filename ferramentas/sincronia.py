"""Monta o episódio Kai com a dublagem brasileira a partir do mapa de segmentos."""

import subprocess
from pathlib import Path

from . import midia

FORMATO = "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
FADE = 0.01  # 10 ms nas emendas evita estalos


def validar_segmentos(segmentos, duracao=None):
    """Lista de problemas encontrados no mapa (vazia = mapa ok)."""
    problemas = []
    if not segmentos:
        return ["o mapa está vazio; rode `python -m ferramentas mapear` primeiro"]
    if abs(segmentos[0]["kai_inicio"]) > 0.001:
        problemas.append("o primeiro segmento deve começar em 0")
    for i, s in enumerate(segmentos):
        if s["kai_fim"] <= s["kai_inicio"]:
            problemas.append(f"segmento {i}: kai_fim deve ser maior que kai_inicio")
        if i and abs(s["kai_inicio"] - segmentos[i - 1]["kai_fim"]) > 0.001:
            problemas.append(f"segmento {i}: há buraco ou sobreposição com o anterior")
        if s.get("origem") is not None and s.get("origem_inicio") is None:
            problemas.append(f"segmento {i}: origem sem origem_inicio")
        if s.get("origem") is None and s.get("preencher", "original") not in ("original", "silencio"):
            problemas.append(f"segmento {i}: preencher deve ser 'original' ou 'silencio'")
    if duracao is not None and abs(segmentos[-1]["kai_fim"] - duracao) > 0.5:
        problemas.append(f"o mapa termina em {segmentos[-1]['kai_fim']}s, mas o vídeo Kai tem {duracao:.3f}s")
    return problemas


def plano_de_audio(segmentos, kai, originais, ajuste_origem_ms=None):
    """Entradas extras do FFmpeg (uma por trecho) e o filtro que as costura na faixa [dub].

    A entrada 0 é sempre o vídeo Kai; cada trecho vira `-ss início -t duração -i arquivo`,
    o que corta com precisão de amostra e não acumula áudio na memória.
    """
    ajuste_origem_ms = ajuste_origem_ms or {}
    entradas, partes, rotulos = [], [], []
    for i, s in enumerate(segmentos):
        dur = s["kai_fim"] - s["kai_inicio"]
        fade = f"afade=t=in:d={FADE},afade=t=out:st={max(dur - FADE, 0):.3f}:d={FADE}"
        if s.get("origem") is not None:
            ini = s["origem_inicio"] + (s.get("ajuste_ms", 0) + ajuste_origem_ms.get(s["origem"], 0)) / 1000
            arquivo, atraso = originais[s["origem"]], max(-ini, 0)  # antes do arquivo: completa com silêncio
            entradas += ["-ss", f"{max(ini, 0):.3f}", "-t", f"{dur - atraso:.3f}", "-i", str(arquivo)]
            cadeia = f"[{len(entradas) // 6}:a:0]{FORMATO}"
            if atraso:
                cadeia += f",adelay={round(atraso * 1000)}:all=1"
        elif s.get("preencher", "original") == "original":
            entradas += ["-ss", f"{s['kai_inicio']:.3f}", "-t", f"{dur:.3f}", "-i", str(kai)]
            cadeia = f"[{len(entradas) // 6}:a:0]{FORMATO}"
        else:
            cadeia = f"anullsrc=r=48000:cl=stereo,{FORMATO}"
        # apad + atrim garante a duração exata de cada trecho, mesmo se o arquivo acabar antes
        partes.append(f"{cadeia},apad,atrim=duration={dur:.3f},{fade}[s{i}]")
        rotulos.append(f"[s{i}]")
    partes.append(f"{''.join(rotulos)}concat=n={len(rotulos)}:v=0:a=1[dub]")
    return entradas, ";\n".join(partes)


def montar_comando(kai, segmentos, originais, saida, arquivo_filtro, ajuste_origem_ms=None,
                   reencodar=None, manter_original=True, titulo=None):
    """Comando FFmpeg completo. `originais` = {número: caminho do original dublado}.

    O filtro vai para `arquivo_filtro` porque episódios longos estouram o limite de
    tamanho da linha de comando do Windows.
    """
    # ponytail: uma entrada por trecho; ~400 trechos ainda cabem na linha de comando do Windows.
    info = midia.sondar(kai)
    entradas, filtro = plano_de_audio(segmentos, kai, originais, ajuste_origem_ms)
    with open(arquivo_filtro, "w", encoding="utf-8") as f:
        f.write(filtro)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "warning", "-stats", "-y", "-i", str(kai), *entradas,
           "-filter_complex_script", str(arquivo_filtro), "-map", "0:v:0", "-map", "[dub]"]
    if manter_original and info["tem_audio"]:
        cmd += ["-map", "0:a:0"]

    # TVs LG (webOS) tocam com segurança H.264 8 bits; HEVC 10 bits falha em vários modelos.
    if reencodar is None:
        reencodar = not (info["codec_video"] == "h264" and info["pix_fmt"] == "yuv420p")
    if reencodar:
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-profile:v", "high"]
    else:
        cmd += ["-c:v", "copy"]
    cmd += ["-c:a", "aac", "-b:a", "192k", "-ac", "2",
            "-metadata:s:a:0", "language=por", "-metadata:s:a:0", "title=Português (Brasil)",
            "-disposition:a:0", "default"]
    if manter_original and info["tem_audio"]:
        cmd += ["-metadata:s:a:1", "language=jpn", "-metadata:s:a:1", "title=Original", "-disposition:a:1", "0"]
    if titulo:
        cmd += ["-metadata", f"title={titulo}"]
    cmd += ["-movflags", "+faststart", str(saida)]
    return cmd


def sincronizar(kai, segmentos, originais, saida, **opcoes):
    problemas = validar_segmentos(segmentos, midia.sondar(kai)["duracao"])
    if problemas:
        raise ValueError("Mapa inválido:\n- " + "\n- ".join(problemas))
    faltando = {s["origem"] for s in segmentos if s.get("origem") is not None} - set(originais)
    if faltando:
        raise ValueError(f"Originais sem caminho no config.local.json: {sorted(faltando)}")
    arquivo_filtro = Path(saida).with_suffix(".filtro.txt")
    subprocess.run(montar_comando(kai, segmentos, originais, saida, arquivo_filtro, **opcoes), check=True)
    arquivo_filtro.unlink()
    return saida
