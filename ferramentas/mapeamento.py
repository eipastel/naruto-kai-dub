"""Mapeia cada trecho do Naruto Kai para o ponto exato do episódio original.

Como funciona, em linguagem simples:
1. O FFmpeg acha os cortes de cena do episódio Kai; cada plano vira um trecho.
2. Cada quadro (Kai e originais) vira uma miniatura 32x18 em tons de cinza.
3. Para cada trecho, procuramos nos originais a sequência de quadros mais parecida.
4. Trechos vizinhos que continuam no mesmo ponto do original são unidos.
5. (Opcional) O áudio afina o encaixe para milissegundos, usando a trilha
   sonora e os efeitos, que são iguais no áudio japonês e no dublado.
"""

import numpy as np

from . import midia

DIMENSAO = midia.LARGURA * midia.ALTURA


def _planos(cortes, duracao, fps):
    """Limites [inicio, fim) de cada plano; planos menores que 2 quadros são absorvidos."""
    limites = [0.0]
    for t in sorted(set(round(c, 3) for c in cortes)):
        if t - limites[-1] >= 2 / fps and duracao - t >= 2 / fps:
            limites.append(t)
    limites.append(duracao)
    return list(zip(limites, limites[1:]))


def _casar(trecho, banco, inicio_origem, fim_origem, candidatos=25):
    """Melhor posição de `trecho` (k x 576) dentro de `banco`. Retorna (indice, correlacao)."""
    meio = len(trecho) // 2
    afinidade = banco @ trecho[meio] / DIMENSAO
    melhor = (None, -1.0)
    for p in np.argsort(afinidade)[::-1][:candidatos]:
        inicio = p - meio
        # o trecho inteiro precisa caber dentro de um único episódio original
        if inicio < inicio_origem[p] or inicio + len(trecho) > fim_origem[p]:
            continue
        janela = banco[inicio:inicio + len(trecho)]
        validos = trecho.any(axis=1) & janela.any(axis=1)
        if not validos.any():
            continue
        corr = float((np.einsum("ij,ij->i", janela, trecho)[validos] / DIMENSAO).mean())
        if corr > melhor[1]:
            melhor = (int(inicio), corr)
    return melhor


def unir(segmentos, tolerancia):
    """Une trechos consecutivos que seguem contínuos no mesmo episódio original."""
    unidos = []
    for s in segmentos:
        if unidos:
            u = unidos[-1]
            mesma_lacuna = u["origem"] is None and s["origem"] is None
            continuo = (
                u["origem"] is not None and u["origem"] == s["origem"]
                and abs((s["origem_inicio"] - s["kai_inicio"]) - (u["origem_inicio"] - u["kai_inicio"])) <= tolerancia
            )
            if mesma_lacuna or continuo:
                u["kai_fim"] = s["kai_fim"]
                if continuo:
                    u["confianca"] = min(u["confianca"], s["confianca"])
                continue
        unidos.append(dict(s))
    return unidos


def mapear(kai, originais, fps=5, limiar_cena=0.35, limiar_quadro=0.5, confianca_minima=0.6,
           filtro_kai=None, filtro_original=None, avisar=print):
    """Gera a lista de segmentos que cobre o episódio Kai do início ao fim.

    `originais` é um dicionário {número do episódio original: caminho do arquivo dublado}.
    """
    duracao = midia.sondar(kai)["duracao"]
    avisar(f"Detectando cortes em {kai} ...")
    cortes = midia.detectar_cortes(kai, limiar_cena, filtro_kai)
    q_kai = midia.quadros(kai, fps, filtro_kai)
    # O filtro `scene` do FFmpeg perde cortes entre cenas de brilho parecido; quadros vizinhos
    # pouco parecidos também contam como corte. Cortes a mais não atrapalham: `unir` junta depois.
    vizinhos = np.einsum("ij,ij->i", q_kai[:-1], q_kai[1:]) / DIMENSAO
    cortes += [(i + 1) / fps for i in np.flatnonzero(vizinhos < limiar_quadro)]
    planos = _planos(cortes, duracao, fps)
    avisar(f"{len(planos)} planos encontrados.")

    blocos, ids, inicio_origem, fim_origem = [], [], [], []
    posicao = 0
    for numero, caminho in sorted(originais.items()):
        avisar(f"Lendo quadros do original {numero} ...")
        q = midia.quadros(caminho, fps, filtro_original)
        blocos.append(q)
        ids += [numero] * len(q)
        inicio_origem += [posicao] * len(q)
        fim_origem += [posicao + len(q)] * len(q)
        posicao += len(q)
    banco = np.concatenate(blocos)
    inicio_origem, fim_origem = np.array(inicio_origem), np.array(fim_origem)

    segmentos = []
    for a, b in planos:
        ia, ib = round(a * fps), min(round(b * fps), len(q_kai))
        seg = {"kai_inicio": round(a, 3), "kai_fim": round(b, 3), "origem": None,
               "origem_inicio": None, "confianca": 0.0, "ajuste_ms": 0}
        if ib > ia:
            p, corr = _casar(q_kai[ia:ib], banco, inicio_origem, fim_origem)
            seg["confianca"] = round(max(corr, 0.0), 3)
            if p is not None and corr >= confianca_minima:
                seg["origem"] = ids[p]
                seg["origem_inicio"] = round(float(a + (p - inicio_origem[p] - ia) / fps), 3)
        segmentos.append(seg)

    resultado = unir(segmentos, tolerancia=1.5 / fps)
    for s in resultado:
        if s["origem"] is None:
            s.update(origem_inicio=None, preencher="original")
    return resultado


def defasagem_audio(referencia, alvo, janela, taxa=8000):
    """Atraso (s) de `referencia` dentro de `alvo`, onde alvo = referência com `janela` s de folga
    de cada lado. Retorna (atraso, força do pico 0..1)."""
    n = len(referencia)
    if n == 0 or len(alvo) < n:
        return 0.0, 0.0
    tamanho = 1 << int(np.ceil(np.log2(len(alvo) + n)))
    corr = np.fft.irfft(np.fft.rfft(alvo, tamanho) * np.conj(np.fft.rfft(referencia, tamanho)), tamanho)
    corr = corr[:len(alvo) - n + 1]
    energia = np.sqrt(np.convolve(alvo ** 2, np.ones(n), "valid"))  # energia de cada janela do alvo
    forca = corr / (np.linalg.norm(referencia) * energia + 1e-9)
    pico = int(np.argmax(forca))
    return (pico - round(janela * taxa)) / taxa, float(forca[pico])


def refinar_por_audio(segmentos, kai, originais, janela=0.5, forca_minima=0.3, avisar=print):
    """Afina `origem_inicio` comparando o áudio original do Kai com o áudio dublado."""
    for s in segmentos:
        duracao = s["kai_fim"] - s["kai_inicio"]
        if s["origem"] is None or duracao < 2:
            continue
        trecho = min(duracao, 10.0)
        ref = midia.audio(kai, s["kai_inicio"], trecho)
        alvo = midia.audio(originais[s["origem"]], s["origem_inicio"] - janela, trecho + 2 * janela)
        if s["origem_inicio"] < janela:  # início do arquivo: completa a folga com silêncio
            alvo = np.concatenate([np.zeros(round((janela - s["origem_inicio"]) * 8000), np.float32), alvo])
        atraso, forca = defasagem_audio(ref, alvo, janela)
        if forca >= forca_minima:
            s["origem_inicio"] = round(float(s["origem_inicio"] + atraso), 3)
        else:
            avisar(f"  trecho {s['kai_inicio']:.2f}s: áudio inconclusivo (força {forca:.2f}); mantido o encaixe por vídeo")
    return segmentos
