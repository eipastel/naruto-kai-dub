"""Transforma um episódio do Naruto clássico em versão "Kai": sem abertura, encerramento,
prévia do próximo episódio e recapitulação do anterior.

Como funciona, em linguagem simples:
- Abertura e encerramento se repetem em vários episódios. Comparamos o episódio com
  episódios próximos (2, 3 e 5 antes e depois): o que se repete no começo é abertura e o que
  se repete no fim é encerramento. Do início do encerramento até o fim sai tudo (a prévia
  do próximo episódio vem depois do encerramento).
- A recapitulação repete cenas do episódio anterior logo depois da abertura.
- Flashbacks no meio do episódio são mantidos.
"""

from pathlib import Path

import numpy as np

from . import midia

FPS = 4
JANELA_ABERTURA = 240   # s: abertura sempre começa nos primeiros 4 minutos
JANELA_FIM = 240        # s: encerramento sempre começa nos últimos 4 minutos
JANELA_RECAP = 240      # s: recapitulação fica até 4 minutos depois da abertura
DURACAO_ABERTURA = 95   # s: abertura (~90 s) + cartela; flashbacks logo depois não entram


def impressoes(video, cache):
    """Impressões digitais dos quadros (4 por segundo), guardadas em cache."""
    arquivo = Path(cache) / (Path(video).stem + ".npy")
    if not arquivo.exists():
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        np.save(arquivo, midia.quadros(video, FPS).astype(np.float16))
    return np.load(arquivo).astype(np.float32)


def repeticoes(a, b, limiar=0.85, minimo=3.0):
    """Trechos [inicio, fim] (s) de `a` que aparecem em sequência dentro de `b`."""
    sim = a @ b.T / midia.LARGURA / midia.ALTURA
    melhor, nota = sim.argmax(1), sim.max(1)
    desvio = melhor - np.arange(len(a))
    trechos, i = [], 0
    while i < len(a):
        if nota[i] <= limiar:
            i += 1
            continue
        k = i
        while k + 1 < len(a) and nota[k + 1] > limiar and abs(desvio[k + 1] - desvio[k]) <= 2:
            k += 1
        if (k - i + 1) / FPS >= minimo:
            trechos.append([i / FPS, (k + 1) / FPS])
        i = k + 1
    return trechos


def juntar(trechos, folga):
    """Une trechos separados por no máximo `folga` segundos."""
    unidos = []
    for ini, fim in sorted(trechos):
        if unidos and ini - unidos[-1][1] <= folga:
            unidos[-1][1] = max(unidos[-1][1], fim)
        else:
            unidos.append([ini, fim])
    return unidos


def detectar(atual, vizinhos, antes, anterior=None):
    """Lista de trechos a remover: [{"inicio", "fim", "motivo"}].

    `atual`, `vizinhos` e `anterior` são matrizes de impressões. `vizinhos` devem ser episódios
    distantes (2, 3 e 5 antes/depois), que compartilham abertura e encerramento mas quase nunca
    cenas da história; `antes[i]` diz se `vizinhos[i]` vem antes deste episódio;
    `anterior` é o episódio imediatamente anterior (para a recapitulação).
    """
    duracao = len(atual) / FPS
    por_vizinho = [repeticoes(atual, v) for v in vizinhos]
    repetidos = [t for trechos in por_vizinho for t in trechos]
    removidos = []

    abertura = juntar([t for t in repetidos if t[0] < JANELA_ABERTURA], folga=30)
    abertura = [t for t in abertura if t[1] - t[0] >= 30]
    fim_abertura = 0.0
    if abertura:
        ini, fim = abertura[0]
        ini = 0.0 if ini <= 2 else ini  # sobra de 1-2 s de tela preta antes da abertura
        # cenas novas logo após a abertura podem reaparecer como flashback nos vizinhos;
        # a abertura nunca passa de ~95 s, e a recapitulação é tratada à parte
        fim = min(fim, ini + DURACAO_ABERTURA)
        removidos.append({"inicio": ini, "fim": fim, "motivo": "abertura"})
        fim_abertura = fim

    # Encerramento: os créditos mudam a cada episódio e quebram a comparação no meio, e a música
    # do encerramento troca de tempos em tempos. Vale o primeiro trecho do fim que:
    #  - se repete em 2+ vizinhos exatamente naquele ponto;
    #  - aparece (até 15 s depois) na maioria dos vizinhos, ou em todos os de um mesmo lado
    #    (antes ou depois), o que cobre a troca de encerramento;
    #  - é seguido de 40 s+ de material repetido até o fim.
    # Cenas da história reaparecem só em alguns vizinhos (recapitulações) e não passam.
    fim = [t for t in repetidos if t[0] > duracao - JANELA_FIM]
    lados = [{i for i, a in enumerate(antes) if a}, {i for i, a in enumerate(antes) if not a}]

    def apoio(ini, tolerancia):
        return {i for i, trechos in enumerate(por_vizinho)
                if any(a <= ini + tolerancia and ini - 1 <= b for a, b in trechos)}

    for ini, _ in sorted(fim):
        exato, perto = apoio(ini, 1), apoio(ini, 15)
        lado_inteiro = any(len(lado) >= 2 and lado <= perto for lado in lados)
        depois = sum(b - a for a, b in juntar([t for t in fim if t[0] >= ini], folga=0))
        if len(exato) >= 2 and (len(perto) > len(vizinhos) / 2 or lado_inteiro) and depois >= 40:
            removidos.append({"inicio": ini, "fim": round(duracao, 2), "motivo": "encerramento e prévia"})
            break

    if anterior is not None:
        limite = fim_abertura + JANELA_RECAP
        # só trechos repetidos de 3 s ou mais estendem a recapitulação; pedaços curtos costumam
        # ser flashbacks rápidos dentro da cena nova
        recap = [t for t in repeticoes(atual, anterior) if fim_abertura - 1 <= t[0] < limite]
        recap = juntar(recap, folga=20)
        if recap and recap[0][0] - fim_abertura <= 15:  # recapitulação vem logo depois da abertura
            removidos.append({"inicio": fim_abertura, "fim": recap[0][1], "motivo": "recapitulação"})

    removidos = sorted(removidos, key=lambda r: r["inicio"])
    for r in removidos:
        r["inicio"], r["fim"] = round(r["inicio"], 2), round(r["fim"], 2)
    # trechos colados viram um só (ex.: abertura seguida de recapitulação)
    final = []
    for r in removidos:
        if final and r["inicio"] - final[-1]["fim"] <= 1.0:
            final[-1]["fim"] = max(final[-1]["fim"], r["fim"])
            final[-1]["motivo"] += " + " + r["motivo"]
        else:
            final.append(r)
    return final


def manter(removidos, duracao):
    """Complemento de `removidos`: os trechos [inicio, fim] que ficam no episódio."""
    trechos, pos = [], 0.0
    for r in sorted(removidos, key=lambda r: r["inicio"]):
        if r["inicio"] > pos:
            trechos.append([pos, r["inicio"]])
        pos = max(pos, r["fim"])
    if duracao - pos > 0.05:
        trechos.append([pos, duracao])
    return trechos


def comando_montagem(video, removidos, saida, codificador="h264_nvenc", titulo=None):
    """Comando FFmpeg que corta os trechos removidos e gera um MP4 pronto para TV LG."""
    trechos = manter(removidos, midia.sondar(video)["duracao"])
    partes = []
    for i, (ini, fim) in enumerate(trechos):
        partes.append(f"[0:v]trim=start={ini:.3f}:end={fim:.3f},setpts=PTS-STARTPTS[v{i}]")
        partes.append(f"[0:a]atrim=start={ini:.3f}:end={fim:.3f},asetpts=PTS-STARTPTS,"
                      f"afade=t=in:d=0.02,afade=t=out:st={max(fim - ini - 0.02, 0):.3f}:d=0.02[a{i}]")
    entradas = "".join(f"[v{i}][a{i}]" for i in range(len(trechos)))
    filtro = ";".join(partes) + f";{entradas}concat=n={len(trechos)}:v=1:a=1[v][a]"
    if codificador == "h264_nvenc":
        video_args = ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "23", "-b:v", "0"]
    else:
        video_args = ["-c:v", "libx264", "-preset", "medium", "-crf", "21"]
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "warning", "-stats", "-y", "-i", str(video),
           "-filter_complex", filtro, "-map", "[v]", "-map", "[a]", *video_args,
           "-profile:v", "high", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-ac", "2",
           "-metadata:s:a:0", "language=por", "-metadata:s:a:0", "title=Português (Brasil)"]
    if titulo:
        cmd += ["-metadata", f"title={titulo}"]
    return cmd + ["-movflags", "+faststart", str(saida)]
