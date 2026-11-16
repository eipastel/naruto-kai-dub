# Fluxo de trabalho

Como levar um episódio do Naruto Kai do seu arquivo local até o Stremio com a dublagem brasileira.

## 1. Preparar o ambiente (uma vez)

```bash
pip install -r requirements.txt
cp config.exemplo.json config.local.json
```

Edite `config.local.json` (ele fica só na sua máquina, nunca vai para o GitHub):

| Campo | O que é |
|---|---|
| `kai` | Caminho de cada episódio do Naruto Kai, pela chave `s01e001`, `s01e002`… |
| `originais_dublados` | Caminho de cada episódio **original** do Naruto com áudio PT-BR, pelo número do episódio. |
| `pasta_saida` | Onde os MP4 finais serão gravados. |
| `filtro_kai` / `filtro_original` | Filtro FFmpeg opcional aplicado antes da comparação (veja “Imagens diferentes” abaixo). |
| `ajuste_origem_ms` | Atraso fixo, em milissegundos, para um episódio original inteiro. Ex.: `{"3": -120}`. |

## 2. Criar o episódio

O episódio 1 já existe. Para os próximos:

```bash
python -m ferramentas novo 2
```

Preencha em `dados/episodios/s01e002.json`:

- `titulo`, `sinopse`, `capitulos_manga` e `adicionado_em` (`AAAA-MM-DD`);
- `originais`: os episódios originais onde o mapeamento deve procurar. Pode colocar alguns a mais por segurança; só deixa a análise um pouco mais lenta.

## 3. Identificar os cortes (opcional)

```bash
python -m ferramentas cortes 1
```

Lista os instantes em que o FFmpeg detecta troca de cena. O `mapear` já faz isso sozinho; este comando serve para conferir. Use `--limiar 0.25` para achar mais cortes ou `--limiar 0.5` para menos.

## 4. Mapear o Kai nos episódios originais

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

## 5. Gerar o episódio dublado

```bash
python -m ferramentas sincronizar 1
```

Gera `Naruto Kai Dublado - S01E001.mp4` na `pasta_saida` com:

- vídeo em **H.264 8 bits** (o formato mais seguro para TVs LG); se o Kai já estiver em H.264, o vídeo é copiado sem perda;
- faixa 1: **Português (Brasil)**, padrão;
- faixa 2: áudio original do Kai (use `--so-dublado` para omitir);
- `faststart`, para começar a tocar rápido pela rede.

## 6. Ajustes manuais

Assista ao MP4. Se uma fala estiver adiantada ou atrasada:

- **um trecho só:** mude `ajuste_ms` daquele item do mapa. Positivo = pega o áudio dublado mais à frente (a fala chega mais cedo); negativo = mais atrás;
- **um episódio original inteiro:** use `ajuste_origem_ms` no `config.local.json`;
- **corte no lugar errado:** edite `kai_inicio`/`kai_fim` de dois itens vizinhos, mantendo o fim de um igual ao início do próximo;
- **trecho sem correspondência:** troque `preencher` entre `original` e `silencio`.

Depois rode `sincronizar` de novo. Ele valida o mapa antes (sem buracos, sem sobreposição, cobrindo o episódio inteiro).

## 7. Disponibilizar o vídeo

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

## 8. Publicar

```bash
npm test          # valida os dados e roda os testes
git add dados && git commit -m "Episódio 2" && git push
```

O GitHub Actions valida, gera e publica. Em poucos minutos o Stremio mostra a mudança — sem reinstalar.

Para testar antes de publicar: `npm run local` e instale `http://127.0.0.1:7000/manifest.json` no Stremio do computador.

## Problemas comuns

**Imagens diferentes entre Kai e original.** Se o Kai foi feito de outra fonte (ex.: 16:9 recortado a partir do 4:3, ou com bordas pretas), a comparação perde precisão. Iguale as duas imagens com filtros FFmpeg no `config.local.json`, por exemplo:

```json
"filtro_kai": "crop=ih*4/3:ih",
"filtro_original": null
```

**Muitos trechos `<- revisar`.** Tente `--fps 8` (mais preciso, mais lento) ou `--confianca 0.5`.

**Áudio “inconclusivo”.** O ajuste pelo áudio não teve certeza e manteve o encaixe pelo vídeo (precisão de ~0,2 s). Confira esses trechos e use `ajuste_ms` se necessário.
