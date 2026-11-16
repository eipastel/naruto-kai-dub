"""Teste de ponta a ponta com mídia sintética gerada pelo próprio FFmpeg (nenhum vídeo real).

Monta dois "episódios originais" e um "Kai" feito de pedaços deles fora de ordem,
mais um trecho inédito. O mapeamento precisa reencontrar cada pedaço e a sincronia
precisa gerar um MP4 com a mesma duração do Kai.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path

from ferramentas import limpeza, mapeamento, midia, sincronia

FONTES = {
    "a1": "testsrc2=s=320x240:r=25", "a2": "mandelbrot=s=320x240:r=25",
    "b1": "cellauto=s=320x240:r=25:seed=7:rule=110", "b2": "life=s=320x240:r=25:seed=3:mold=10",
}


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def gerar_original(destino, partes, sementes):
    entradas, filtros = [], []
    for i, (fonte, semente) in enumerate(zip(partes, sementes)):
        entradas += ["-f", "lavfi", "-t", "4", "-i", FONTES[fonte],
                     "-f", "lavfi", "-t", "4", "-i", f"anoisesrc=r=48000:a=0.3:seed={semente}"]
        filtros.append(f"[{2 * i}:v]format=yuv420p[v{i}];[{2 * i + 1}:a]aformat=channel_layouts=stereo[a{i}]")
    junta = "".join(f"[v{i}][a{i}]" for i in range(len(partes)))
    ffmpeg(*entradas, "-filter_complex", ";".join(filtros) + f";{junta}concat=n={len(partes)}:v=1:a=1[v][a]",
           "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(destino))


class PontaAPonta(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        d = Path(cls.dir.name)
        cls.a, cls.b, cls.kai = d / "orig1.mp4", d / "orig2.mp4", d / "kai.mp4"
        gerar_original(cls.a, ["a1", "a2"], [1, 2])
        gerar_original(cls.b, ["b1", "b2"], [3, 4])
        # Kai = A[1–3] + B[4.5–7.5] + trecho inédito (vermelho) + A[5–8]
        ffmpeg("-i", str(cls.a), "-i", str(cls.b), "-f", "lavfi", "-t", "2", "-i", "color=red:s=320x240:r=25",
               "-f", "lavfi", "-t", "2", "-i", "sine=f=440:r=48000",
               "-filter_complex",
               "[0:v]trim=1:3,setpts=PTS-STARTPTS[v0];[0:a]atrim=1:3,asetpts=PTS-STARTPTS[a0];"
               "[1:v]trim=4.5:7.5,setpts=PTS-STARTPTS[v1];[1:a]atrim=4.5:7.5,asetpts=PTS-STARTPTS[a1];"
               "[2:v]format=yuv420p[v2];[3:a]aformat=channel_layouts=stereo[a2];"
               "[0:v]trim=5:8,setpts=PTS-STARTPTS[v3];[0:a]atrim=5:8,asetpts=PTS-STARTPTS[a3];"
               "[v0][a0][v1][a1][v2][a2][v3][a3]concat=n=4:v=1:a=1[v][a]",
               "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(cls.kai))
        cls.mapa = mapeamento.mapear(cls.kai, {1: cls.a, 2: cls.b}, avisar=lambda *_: None)
        mapeamento.refinar_por_audio(cls.mapa, cls.kai, {1: cls.a, 2: cls.b}, avisar=lambda *_: None)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_mapeamento_reencontra_cada_trecho(self):
        esperado = [(0, 1, 1.0), (2, 2, 4.5), (5, None, None), (7, 1, 5.0)]
        self.assertEqual(len(self.mapa), len(esperado), self.mapa)
        for seg, (kai_ini, origem, origem_ini) in zip(self.mapa, esperado):
            self.assertAlmostEqual(seg["kai_inicio"], kai_ini, delta=0.1)
            self.assertEqual(seg["origem"], origem, seg)
            if origem is not None:
                self.assertAlmostEqual(seg["origem_inicio"], origem_ini, delta=0.05, msg=seg)
        self.assertEqual(sincronia.validar_segmentos(self.mapa, midia.sondar(self.kai)["duracao"]), [])

    def test_corte_que_o_filtro_scene_nao_ve(self):
        # cellauto -> mandelbrot: o filtro `scene` do FFmpeg não detecta essa troca
        kai2 = Path(self.dir.name) / "kai2.mp4"
        ffmpeg("-i", str(self.b), "-i", str(self.a), "-filter_complex",
               "[0:v]trim=0.5:3.5,setpts=PTS-STARTPTS[v0];[0:a]atrim=0.5:3.5,asetpts=PTS-STARTPTS[a0];"
               "[1:v]trim=4:7,setpts=PTS-STARTPTS[v1];[1:a]atrim=4:7,asetpts=PTS-STARTPTS[a1];"
               "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]",
               "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(kai2))
        mapa = mapeamento.mapear(kai2, {1: self.a, 2: self.b}, avisar=lambda *_: None)
        self.assertEqual([s["origem"] for s in mapa], [2, 1], mapa)
        for seg, esperado in zip(mapa, [0.5, 4.0]):
            self.assertAlmostEqual(seg["origem_inicio"], esperado, delta=0.25, msg=mapa)

    def test_sincronia_gera_mp4_com_duas_faixas_e_mesma_duracao(self):
        saida = Path(self.dir.name) / "saida.mp4"
        sincronia.sincronizar(self.kai, self.mapa, {1: self.a, 2: self.b}, saida)
        self.assertAlmostEqual(midia.sondar(saida)["duracao"], midia.sondar(self.kai)["duracao"], delta=0.15)
        faixas = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                                 "stream_tags=language", "-of", "csv=p=0", str(saida)],
                                capture_output=True, text=True).stdout.split()
        self.assertEqual(faixas, ["por", "jpn"])


class Limpeza(unittest.TestCase):
    """Episódios falsos feitos de 'quadros' aleatórios: abertura e encerramento iguais em todos,
    história diferente em cada um, e o episódio 2 começa recapitulando o fim do episódio 1."""

    def setUp(self):
        import numpy as np
        rng = np.random.default_rng(1)
        quadros = lambda s: rng.standard_normal((int(s * limpeza.FPS), 576)).astype(np.float32)  # noqa: E731
        abertura, encerramento = quadros(90), quadros(120)
        self.historias = [quadros(1100) for _ in range(6)]
        self.eps = [np.concatenate([abertura, h, encerramento]) for h in self.historias]
        recap = self.historias[0][-60 * limpeza.FPS:]  # último minuto do episódio 1
        self.eps[1] = np.concatenate([abertura, recap, self.historias[1], encerramento])

    def test_detecta_abertura_recapitulacao_e_encerramento(self):
        rem = limpeza.detectar(self.eps[1], [self.eps[3], self.eps[4], self.eps[5]], [False] * 3, self.eps[0])
        self.assertEqual([r["motivo"] for r in rem], ["abertura + recapitulação", "encerramento e prévia"])
        self.assertAlmostEqual(rem[0]["inicio"], 0, delta=0.5)
        self.assertAlmostEqual(rem[0]["fim"], 150, delta=0.5)
        self.assertAlmostEqual(rem[1]["inicio"], 1250, delta=0.5)

    def test_cena_repetida_em_um_so_vizinho_nao_vira_encerramento(self):
        # o fim da história do episódio 3 reaparece só no episódio 5 (como numa recapitulação)
        import numpy as np
        ep5 = np.concatenate([self.historias[2][-100 * limpeza.FPS:], self.eps[4]])
        rem = limpeza.detectar(self.eps[2], [self.eps[0], self.eps[1], ep5], [True, True, False], self.eps[1])
        self.assertAlmostEqual(rem[-1]["inicio"], 1190, delta=0.5)

    def test_manter_e_complemento_de_removidos(self):
        rem = [{"inicio": 0, "fim": 100}, {"inicio": 1200, "fim": 1400}]
        self.assertEqual(limpeza.manter(rem, 1400), [[100, 1200]])


class Unidades(unittest.TestCase):
    def test_unir_trechos_continuos(self):
        segs = [
            {"kai_inicio": 0, "kai_fim": 2, "origem": 1, "origem_inicio": 10.0, "confianca": 0.9},
            {"kai_inicio": 2, "kai_fim": 5, "origem": 1, "origem_inicio": 12.1, "confianca": 0.8},
            {"kai_inicio": 5, "kai_fim": 6, "origem": None, "origem_inicio": None, "confianca": 0.1},
            {"kai_inicio": 6, "kai_fim": 7, "origem": None, "origem_inicio": None, "confianca": 0.2},
        ]
        unidos = mapeamento.unir(segs, tolerancia=0.3)
        self.assertEqual([(s["kai_inicio"], s["kai_fim"], s["origem"]) for s in unidos], [(0, 5, 1), (5, 7, None)])
        self.assertEqual(unidos[0]["confianca"], 0.8)

    def test_validacao_aponta_buraco(self):
        segs = [{"kai_inicio": 0, "kai_fim": 2, "origem": None}, {"kai_inicio": 2.5, "kai_fim": 3, "origem": None}]
        self.assertTrue(any("buraco" in p for p in sincronia.validar_segmentos(segs)))

    def test_defasagem_audio(self):
        import numpy as np
        ruido = np.random.default_rng(0).standard_normal(8000 * 3).astype(np.float32)
        ref = ruido[4000 + 800: 4000 + 800 + 8000]  # referência começa 0,1 s depois do centro da janela
        atraso, forca = mapeamento.defasagem_audio(ref, ruido[:8000 + 8000], janela=0.5)
        self.assertAlmostEqual(atraso, 0.1, places=3)
        self.assertGreater(forca, 0.9)


if __name__ == "__main__":
    unittest.main()
