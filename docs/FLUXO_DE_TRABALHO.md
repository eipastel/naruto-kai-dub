# Fluxo de trabalho

Há dois modos. O **modo clássico** é o principal: gera o "Kai" a partir dos episódios do Naruto clássico dublado. O **modo Kai** usa um arquivo do Naruto Kai como molde e encaixa a dublagem nele (veja o apêndice).

## 1. Preparar (uma vez)

```bash
pip install -r requirements.txt
cp config.exemplo.json config.local.json
```

No `config.local.json` (fica só na sua máquina):

| Campo | O que é |
|---|---|
| `classico.pasta` | Pasta com os episódios dublados do clássico. |
| `classico.arquivo` | Nome dos arquivos, com `{n:03d}` no lugar do número. Ex.: `Naruto Dublado Episodio {n:03d} HD MQ.mp4`. |
| `pasta_saida` | Onde ficam os MP4 prontos (e o cache da análise, em `.impressoes`). |
| `codificador` | `h264_nvenc` (placa NVIDIA, ~1 min por episódio) ou `libx264` (processador, mais lento). |
| `url_streams` | Endereço do servidor da sua casa, ex.: `http://192.168.1.12:8642`. Use o IP que `python -m ferramentas servir` mostrar. |

## 2. Detectar o que cortar

```bash
python -m ferramentas limpar          # todos os 127 episódios canônicos
python -m ferramentas limpar 20-30    # só alguns
```

Para cada episódio é criado `dados/episodios/s01eNNN.json` com título, sinopse, miniatura e a lista `removidos`:

```json
"removidos": [
  { "inicio": 0.0,     "fim": 152.5,  "motivo": "abertura + recapitulação" },
  { "inicio": 1294.25, "fim": 1416.75, "motivo": "encerramento e prévia" }
]
```

Como a detecção funciona:

- **Abertura:** o que se repete no começo dos episódios próximos (2, 3 e 5 antes e depois).
- **Encerramento e prévia:** o primeiro trecho do fim que se repete na maioria dos vizinhos; dali até o final sai tudo.
- **Recapitulação:** logo depois da abertura, o que repete cenas do episódio anterior.
- Flashbacks no meio do episódio são mantidos.

A primeira rodada lê todos os vídeos (~12 s por episódio); as seguintes usam o cache.

## 3. Revisar (opcional)

Edite `inicio`/`fim` em `removidos` se algum corte ficou adiantado ou atrasado, ou apague um item para manter o trecho. Marque `"revisado": true` para o `limpar` não sobrescrever seu ajuste.

## 4. Montar os vídeos

```bash
python -m ferramentas montar          # todos
python -m ferramentas montar 5        # só um
python -m ferramentas montar 5 --forcar   # refaz depois de um ajuste
```

Gera `Naruto Kai Dublado - E005.mp4` na `pasta_saida` (H.264 8 bits + AAC, `faststart`, ideal para TV LG) e registra o link em `streams`.

## 5. Assistir na TV

```bash
python -m ferramentas servir
```

Deixe rodando no computador enquanto assiste. O servidor aceita avançar/voltar. Dica: reserve o IP do computador no roteador para o endereço não mudar.

## 6. Publicar

```bash
npm test
git add dados && git commit -m "Episódios" && git push
```

O GitHub Actions valida e publica; o Stremio mostra as mudanças sem reinstalar. Para testar antes: `npm run local` e instale `http://127.0.0.1:7000/manifest.json` no Stremio do computador.

## Títulos e sinopses

O catálogo usa `dados/textos.json`: título próprio, curto e sem spoiler, e uma sinopse que começa com "Antes:" e resume o episódio **anterior** do catálogo (pulando fillers). Para mudar um texto, edite esse arquivo e faça `git push`.

`dados/classico.json` (referência da Wikipédia em português e miniaturas do Stremio) é gerado por:

```bash
python scripts/importar_metadados.py
```

---

## Apêndice: modo Kai

Use quando tiver os arquivos do próprio Naruto Kai. No `config.local.json`, preencha `kai` (`{"s01e001": "caminho do Kai 1"}`) e `originais_dublados` (`{"1": "caminho do episódio 1 dublado", ...}`).

### Criar o episódio

O episódio 1 já existe. Para os próximos:

```bash
python -m ferramentas novo 2
```

Preencha em `dados/episodios/s01e002.json`:

- `titulo`, `sinopse`, `capitulos_manga` e `adicionado_em` (`AAAA-MM-DD`);
- `originais`: os episódios originais onde o mapeamento deve procurar. Pode colocar alguns a mais por segurança; só deixa a análise um pouco mais lenta.

### Identificar os cortes (opcional)

```bash
python -m ferramentas cortes 1
```

Lista os instantes em que o FFmpeg detecta troca de cena. O `mapear` já faz isso sozinho; este comando serve para conferir. Use `--limiar 0.25` para achar mais cortes ou `--limiar 0.5` para menos.

### Mapear o Kai nos episódios originais

```bash
python -m ferramentas mapear 1
```

O que acontece:

1. cada plano do Kai é comparado com todos os quadros dos originais listados;
2. o trecho recebe o episódio de origem e o segundo exato onde começa lá;
3. o áudio afina o encaixe para a casa dos milissegundos (a trilha sonora e os efeitos são iguais no áudio japonês e no dublado);
4. o resultado é gravado no campo `mapa` do JSON e mostrado numa tabela. Trechos com confiança abaixo de 0,80 aparecem marcados com `<- revisar`.

Cada item do mapa:

```json
{
  "kai_inicio": 83.4,
  "kai_fim": 97.12,
  "origem": 2,
  "origem_inicio": 412.88,
  "confianca": 0.94,
  "ajuste_ms": 0
}
```

Trechos que não existem nos originais (vinhetas e cartelas novas do Kai) ficam com `"origem": null` e `"preencher": "original"` (usa o áudio do próprio Kai) ou `"silencio"`.

Para refazer um mapa que já existe, use `--forcar` (isso apaga os ajustes manuais).

### Gerar o episódio dublado

```bash
python -m ferramentas sincronizar 1
```

Gera `Naruto Kai Dublado - S01E001.mp4` na `pasta_saida` com:

- vídeo em **H.264 8 bits** (o formato mais seguro para TVs LG); se o Kai já estiver em H.264, o vídeo é copiado sem perda;
- faixa 1: **Português (Brasil)**, padrão;
- faixa 2: áudio original do Kai (use `--so-dublado` para omitir);
- `faststart`, para começar a tocar rápido pela rede.

### Ajustes manuais

Assista ao MP4. Se uma fala estiver adiantada ou atrasada:

- **um trecho só:** mude `ajuste_ms` daquele item do mapa. Positivo = pega o áudio dublado mais à frente (a fala chega mais cedo); negativo = mais atrás;
- **um episódio original inteiro:** use `ajuste_origem_ms` no `config.local.json`;
- **corte no lugar errado:** edite `kai_inicio`/`kai_fim` de dois itens vizinhos, mantendo o fim de um igual ao início do próximo;
- **trecho sem correspondência:** troque `preencher` entre `original` e `silencio`.

Depois rode `sincronizar` de novo. Ele valida o mapa antes (sem buracos, sem sobreposição, cobrindo o episódio inteiro).

### Disponibilizar o vídeo

O repositório **não hospeda vídeo**. Você escolhe onde o seu MP4 fica:

- **Rede de casa:** `python -m ferramentas servir` mostra um link como `http://192.168.0.10:8642/Naruto%20Kai%20Dublado%20-%20S01E001.mp4`. O servidor aceita avançar/voltar, o que a TV precisa. O computador precisa estar ligado durante a reprodução.
- **Seu próprio servidor ou mídia de sua posse:** qualquer URL `https://`.

Adicione a fonte em `streams` do episódio:

```json
"streams": [
  { "url": "http://192.168.0.10:8642/Naruto%20Kai%20Dublado%20-%20S01E001.mp4", "title": "1080p · rede de casa" }
]
```

Formatos aceitos: `url`, `infoHash` (+ `fileIdx`), `ytId` ou `externalUrl` — exatamente um por item.

> Lembre: o repositório é público. Só publique links para conteúdo que você tem direito de compartilhar. Links da rede local só funcionam dentro da sua casa.

### Publicar

```bash
npm test          # valida os dados e roda os testes
git add dados && git commit -m "Episódio 2" && git push
```

O GitHub Actions valida, gera e publica. Em poucos minutos o Stremio mostra a mudança — sem reinstalar.

Para testar antes de publicar: `npm run local` e instale `http://127.0.0.1:7000/manifest.json` no Stremio do computador.

### Problemas comuns

**Imagens diferentes entre Kai e original.** Se o Kai foi feito de outra fonte (ex.: 16:9 recortado a partir do 4:3, ou com bordas pretas), a comparação perde precisão. Iguale as duas imagens com filtros FFmpeg no `config.local.json`, por exemplo:

```json
"filtro_kai": "crop=ih*4/3:ih",
"filtro_original": null
```

**Muitos trechos `<- revisar`.** Tente `--fps 8` (mais preciso, mais lento) ou `--confianca 0.5`.

**Áudio “inconclusivo”.** O ajuste pelo áudio não teve certeza e manteve o encaixe pelo vídeo (precisão de ~0,2 s). Confira esses trechos e use `ajuste_ms` se necessário.
