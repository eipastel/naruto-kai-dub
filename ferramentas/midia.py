"""Acesso ao FFmpeg/FFprobe: duração, detecção de cortes, quadros e áudio em memória."""

import json
import re
import subprocess

import numpy as np

LARGURA, ALTURA = 32, 18  # miniatura usada como "impressão digital" de cada quadro


def _rodar(cmd, binario=False):
    proc = subprocess.run(cmd, capture_output=True, text=not binario)
    if proc.returncode != 0:
        erro = proc.stderr if not binario else proc.stderr.decode(errors="replace")
        raise RuntimeError(f"Falha ao executar {cmd[0]}:\n{erro[-2000:]}")
    return proc


def sondar(caminho):
    """Retorna duração (s) e informações do primeiro fluxo de vídeo."""
    saida = _rodar([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(caminho),
    ]).stdout
    dados = json.loads(saida)
    video = next((s for s in dados["streams"] if s["codec_type"] == "video"), {})
    return {
        "duracao": float(dados["format"]["duration"]),
        "codec_video": video.get("codec_name"),
        "pix_fmt": video.get("pix_fmt"),
        "tem_audio": any(s["codec_type"] == "audio" for s in dados["streams"]),
    }


def detectar_cortes(caminho, limiar=0.35, filtro=None):
    """Instantes (s) em que o FFmpeg detecta troca de cena (filtro `scene`)."""
    cadeia = f"select='gt(scene,{limiar})',showinfo"
    if filtro:
        cadeia = f"{filtro},{cadeia}"
    stderr = _rodar([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(caminho),
        "-an", "-vf", cadeia, "-f", "null", "-",
    ]).stderr
    return [float(t) for t in re.findall(r"pts_time:([\d.]+)", stderr)]


def quadros(caminho, fps, filtro=None):
    """Matriz (n_quadros, 576) com miniaturas em tons de cinza, normalizadas.

    Cada linha tem média 0 e desvio 1, então o produto escalar entre duas linhas
    dividido por 576 é a correlação entre os quadros (1 = idênticos).
    """
    cadeia = f"fps={fps},scale={LARGURA}:{ALTURA}:flags=area,format=gray"
    if filtro:
        cadeia = f"{filtro},{cadeia}"
    bruto = _rodar([
        "ffmpeg", "-hide_banner", "-nostats", "-loglevel", "error", "-i", str(caminho),
        "-an", "-vf", cadeia, "-f", "rawvideo", "-",
    ], binario=True).stdout
    q = np.frombuffer(bruto, np.uint8).reshape(-1, LARGURA * ALTURA).astype(np.float32)
    q -= q.mean(axis=1, keepdims=True)
    desvio = q.std(axis=1, keepdims=True)
    # ponytail: quadros chapados (preto/branco) ficam zerados e nunca casam; é o desejado.
    return np.divide(q, desvio, out=np.zeros_like(q), where=desvio > 2)


def audio(caminho, inicio, duracao, taxa=8000):
    """Trecho de áudio mono em float32 (para refinar a sincronia por correlação)."""
    bruto = _rodar([
        "ffmpeg", "-hide_banner", "-nostats", "-loglevel", "error",
        "-ss", f"{max(inicio, 0):.3f}", "-t", f"{duracao:.3f}", "-i", str(caminho),
        "-vn", "-ac", "1", "-ar", str(taxa), "-f", "f32le", "-",
    ], binario=True).stdout
    return np.frombuffer(bruto, np.float32)
