"""Servidor HTTP mínimo com suporte a Range, para a TV conseguir avançar e voltar o vídeo.

O `python -m http.server` padrão não aceita Range, e sem isso a TV não navega no vídeo.
Use só na sua rede local, com arquivos gerados a partir das suas próprias mídias.
"""

import os
import re
import socket
import ssl
import time
import urllib.request
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


CERTIFICADO = "https://local-ip.sh/"  # certificado Let's Encrypt para *.local-ip.sh (chave pública de propósito)


def certificado(pasta):
    """Baixa (ou renova, se tiver mais de 7 dias) o certificado do local-ip.sh."""
    pasta.mkdir(parents=True, exist_ok=True)
    for nome in ("server.pem", "server.key"):
        arquivo = pasta / nome
        if not arquivo.exists() or time.time() - arquivo.stat().st_mtime > 7 * 86400:
            with urllib.request.urlopen(CERTIFICADO + nome, timeout=30) as resposta:
                arquivo.write_bytes(resposta.read())
    return pasta / "server.pem", pasta / "server.key"


def servir(pasta, porta, https=True):
    """Serve os MP4 da pasta. Com https, o endereço é https://192-168-x-x.local-ip.sh:porta,
    porque o Stremio (web e TVs) bloqueia vídeo em http://."""
    pasta.mkdir(parents=True, exist_ok=True)
    ip = ip_local()
    base = f"https://{ip.replace('.', '-')}.local-ip.sh:{porta}" if https else f"http://{ip}:{porta}"
    handler = lambda *a, **k: ComRange(*a, directory=str(pasta), **k)  # noqa: E731
    servidor = ThreadingHTTPServer(("0.0.0.0", porta), handler)
    if https:
        contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        contexto.load_cert_chain(*certificado(pasta / ".certificado"))
        servidor.socket = contexto.wrap_socket(servidor.socket, server_side=True)
    print(f"Servindo {pasta} em {base}/  (Ctrl+C para parar)", flush=True)
    print(f"No config.local.json, use: \"url_streams\": \"{base}\"", flush=True)
    servidor.serve_forever()
