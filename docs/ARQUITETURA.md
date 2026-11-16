# Arquitetura

## Visão geral

```text
 seus arquivos locais                         repositório público
 ┌───────────────────┐   python -m ferramentas   ┌──────────────────────────┐
 │ Naruto Kai (vídeo)│ ─────── mapear ─────────▶ │ dados/episodios/*.json    │
 │ Naruto dublado    │                           │  (metadados, mapa, links) │
 └───────────────────┘ ───── sincronizar ──▶ MP4 └────────────┬─────────────┘
                                                              │ git push
                                                              ▼
                                           GitHub Actions: valida → testa → gera dist/
                                                              │
                                                              ▼
                                  GitHub Pages: manifest.json, catalog/, meta/, stream/
                                                              │
                                                              ▼
                                       Stremio (PC, celular, TV LG) lê os JSON
```

## Complemento Stremio estático

O Stremio aceita complementos que são só arquivos JSON em endereços fixos. Não há servidor rodando: o GitHub Pages entrega os arquivos com HTTPS e CORS liberado, que é o que o Stremio exige.

| Endereço | Conteúdo |
|---|---|
| `/manifest.json` | Identidade do complemento, recursos e catálogo |
| `/catalog/series/nkdub.json` | A série no catálogo |
| `/meta/series/nkdub.json` | Detalhes da série e a lista de episódios |
| `/stream/series/nkdub-<temporada>-<episódio>.json` | Fontes de vídeo do episódio |

**Atualização sem reinstalar.** O Stremio guarda só o endereço do manifesto e busca catálogo, metadados e fontes a cada acesso. Novos episódios, títulos e links aparecem sozinhos depois do `git push` (o GitHub Pages pode levar até ~10 minutos por causa do cache). Só é preciso reinstalar se mudar o `id` do manifesto ou a lista de recursos.

**Identificadores sem dois-pontos.** Os episódios usam `nkdub-1-1` em vez do comum `nkdub:1:1`, porque `:` é proibido em nomes de arquivo no Windows. Assim o projeto funciona igual em qualquer sistema.

**Fonte única de verdade.** `dados/` é editado à mão ou pelas ferramentas; `dist/` é sempre gerado por `scripts/build.mjs` e nunca vai para o Git.

## Compatibilidade com TVs LG

- Tudo servido por HTTPS com JSON pequeno e imagens PNG.
- O MP4 gerado usa H.264 8 bits (perfil High) + AAC estéreo, combinação que o webOS reproduz sem transcodificação. HEVC 10 bits é recodificado automaticamente.
- `+faststart` coloca o índice do MP4 no início, para a TV começar a tocar sem baixar o arquivo inteiro.
- O servidor local (`python -m ferramentas servir`) responde a pedidos `Range`, necessários para avançar e voltar.

> Ainda não foi feito teste em uma TV LG física; as escolhas acima seguem os formatos documentados como suportados pelo webOS.

## Ferramentas (Python + FFmpeg)

| Módulo | Papel |
|---|---|
| `ferramentas/limpeza.py` | Modo clássico: detecta abertura, encerramento, prévia e recapitulação e monta o MP4 enxuto. |
| `ferramentas/midia.py` | Chama `ffprobe`/`ffmpeg`: duração, cortes de cena, miniaturas dos quadros, trechos de áudio. |
| `ferramentas/mapeamento.py` | Encontra a origem de cada trecho do Kai e refina pelo áudio. |
| `ferramentas/sincronia.py` | Valida o mapa e monta o comando FFmpeg que costura a dublagem. |
| `ferramentas/servidor.py` | Servidor HTTP com `Range` para a rede local. |
| `ferramentas/__main__.py` | Linha de comando (`limpar`, `montar`, `servir`; modo Kai: `novo`, `cortes`, `mapear`, `sincronizar`). |

### Limpeza (modo clássico)

Cada episódio é comparado, quadro a quadro, com episódios próximos usando as mesmas impressões digitais do mapeamento (4 quadros por segundo, guardadas em cache):

1. **Abertura:** trechos repetidos nos primeiros 4 minutos, unidos quando separados por até 30 s (os créditos mudam e quebram a comparação).
2. **Encerramento:** o primeiro trecho dos últimos 4 minutos que se repete em 2+ vizinhos naquele ponto exato e aparece na maioria deles (ou em todos de um mesmo lado, quando a música do encerramento acabou de mudar). Cenas da história que reaparecem em recapitulações de episódios seguintes não passam nesse filtro. Dali até o fim sai tudo, inclusive a prévia.
3. **Recapitulação:** logo após a abertura, trechos de 3 s+ que repetem o episódio anterior.

A montagem corta com `trim`/`atrim` + `concat` numa única passada, com 20 ms de fade no áudio das emendas, e codifica com NVENC (ou libx264).

### Arte e metadados

Pôster, fundo, logo e miniaturas vêm do serviço de imagens do próprio Stremio (metahub), os mesmos que o app mostra para Naruto; nada é guardado no repositório. Títulos e sinopses em PT-BR vêm da Wikipédia (CC BY-SA 4.0) via `scripts/importar_metadados.py`.

### Mapeamento (modo Kai)

1. **Cortes:** filtro `scene` do FFmpeg no Kai. Cada intervalo entre cortes é um plano.
2. **Impressão digital:** cada quadro (5 por segundo) vira uma miniatura 32×18 em cinza, normalizada (média 0, desvio 1). Isso ignora diferenças de brilho, resolução e compressão.
3. **Busca:** o quadro central do plano é comparado com todos os quadros dos originais de uma vez (multiplicação de matrizes). Os 25 melhores candidatos são verificados com o plano inteiro; vence a maior correlação média.
4. **União:** planos seguidos que continuam no mesmo ponto do original viram um só segmento.
5. **Refino pelo áudio:** correlação cruzada (FFT) entre o áudio do Kai e o dublado, numa janela de ±0,5 s. Música e efeitos são os mesmos nas duas versões, então o pico mostra o encaixe exato. Se o pico for fraco, mantém-se o encaixe por vídeo.

### Sincronia (modo Kai)

Cada segmento vira uma entrada `-ss início -t duração -i arquivo` do FFmpeg, cortada com precisão de amostra. As partes são padronizadas (48 kHz, estéreo), ganham 10 ms de fade nas emendas para evitar estalos, e são unidas com `concat`. O filtro vai para um arquivo temporário, porque episódios longos estourariam o limite da linha de comando do Windows.

## Testes e CI

`tests/test_ferramentas.py` gera mídia sintética com o próprio FFmpeg (padrões de teste e ruído), monta um “Kai” com pedaços fora de ordem e um trecho inédito, e confere se o mapeamento reencontra cada pedaço e se o MP4 final tem a duração e as faixas certas. Nenhum vídeo real é usado.

O workflow `.github/workflows/publicar.yml` roda em todo push e pull request: valida os dados, roda os testes, gera o complemento e, na `main`, publica no GitHub Pages.

## Como escalar

- **Novo episódio clássico:** `limpar N` + `montar N` + `git push`. Nenhum código muda.
- **Shippuden:** mesma limpeza; basta outra pasta/padrão de arquivo e uma nova temporada.
- **Nova temporada (extras, filmes):** criar `s02e001.json` e incluir a temporada em `dados/serie.json`.
- **Mais de uma fonte por episódio:** adicionar mais itens em `streams` (ex.: 720p e 1080p).
