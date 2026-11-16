"""Servidor HTTP mínimo com suporte a Range, para a TV conseguir avançar e voltar o vídeo.

O `python -m http.server` padrão não aceita Range, e sem isso a TV não navega no vídeo.
Use só na sua rede local, com arquivos gerados a partir das suas próprias mídias.
"""

import os
import re
import socket
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote


class ComRange(SimpleHTTPRequestHandler):
    def send_head(self):
        self.restante = None
        caminho = self.translate_path(self.path)
        intervalo = self.headers.get("Range")
        if not intervalo or not os.path.isfile(caminho):
            return super().send_head()
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", intervalo.strip())
        tamanho = os.path.getsize(caminho)
        if not m or (not m[1] and not m[2]):
            self.send_error(416)
            return None
        inicio = int(m[1]) if m[1] else tamanho - int(m[2])
        fim = int(m[2]) if m[1] and m[2] else tamanho - 1
        fim = min(fim, tamanho - 1)
        if inicio > fim or inicio < 0:
            self.send_error(416)
            return None
        arquivo = open(caminho, "rb")
        arquivo.seek(inicio)
        self.restante = fim - inicio + 1
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(caminho))
        self.send_header("Content-Range", f"bytes {inicio}-{fim}/{tamanho}")
        self.send_header("Content-Length", str(self.restante))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        return arquivo

    def copyfile(self, origem, destino):
        restante = self.restante
        if restante is None:
            return super().copyfile(origem, destino)
        while restante > 0:
            bloco = origem.read(min(1 << 16, restante))
            if not bloco:
                break
            destino.write(bloco)
            restante -= len(bloco)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()


def ip_local():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("192.168.0.1", 9))  # não envia nada; só descobre a interface da rede local
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def servir(pasta, porta):
    pasta.mkdir(parents=True, exist_ok=True)
    ip = ip_local()
    print(f"Servindo {pasta} em http://{ip}:{porta}/  (Ctrl+C para parar)", flush=True)
    for arquivo in sorted(pasta.glob("*.mp4")):
        print(f"  http://{ip}:{porta}/{quote(arquivo.name)}", flush=True)
    handler = lambda *a, **k: ComRange(*a, directory=str(pasta), **k)  # noqa: E731
    ThreadingHTTPServer(("0.0.0.0", porta), handler).serve_forever()
