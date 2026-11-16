<p align="center"><img src="https://images.metahub.space/logo/medium/tt0409591/img" alt="Naruto" width="380"></p>

<h1 align="center">Naruto Kai Dublado</h1>

<p align="center">
  <a href="https://github.com/eipastel/naruto-kai-dub/actions/workflows/publicar.yml"><img src="https://github.com/eipastel/naruto-kai-dub/actions/workflows/publicar.yml/badge.svg" alt="Validar e publicar"></a>
  <img src="https://img.shields.io/badge/Stremio-complemento-7b5bf5" alt="Stremio">
  <img src="https://img.shields.io/badge/idioma-PT--BR-009c3b" alt="PT-BR">
  <img src="https://img.shields.io/badge/licen%C3%A7a-MIT-blue" alt="MIT">
</p>

Complemento (addon) do **Stremio** com o **Naruto clássico dublado em português**, no estilo **Kai**: só a história do mangá, sem fillers, aberturas, encerramentos, prévias e recapitulações. Cada episódio original vira um episódio enxuto de ~19 minutos. Funciona no computador, no celular e nas **Smart TVs LG**.

O projeto tem duas partes:

1. **Complemento Stremio**: arquivos JSON estáticos no GitHub Pages. Títulos, sinopses e links mudam com um `git push`, **sem reinstalar** o complemento.
2. **Ferramentas Python + FFmpeg**: encontram sozinhas a abertura, o encerramento, a prévia e a recapitulação de cada episódio (comparando os episódios entre si), cortam e geram MP4 prontos para a TV. Tudo pode ser ajustado à mão.

> **Aviso legal.** Este repositório **não contém nem distribui vídeos ou áudios**. As ferramentas trabalham com arquivos locais do usuário e o complemento aponta só para fontes que ele mesmo configurar. Naruto © Masashi Kishimoto / Shueisha · Studio Pierrot.

## Instalação no Stremio

```text
https://eipastel.github.io/naruto-kai-dub/manifest.json
```

- **Computador/celular:** abra <https://eipastel.github.io/naruto-kai-dub/> e clique em **Instalar no Stremio**.
- **TV LG:** no Stremio da TV, vá em *Complementos*, cole o endereço na busca e instale. Ou instale no computador com a mesma conta: a TV sincroniza.

Os vídeos tocam a partir do computador onde os MP4 foram gerados (`python -m ferramentas servir`), na mesma rede de casa.

## O que entra

| Arco | Episódios originais |
|---|---|
| Prólogo | 1–5 |
| País das Ondas | 6–19 |
| Exame Chunin | 20–67 (sem o 26, recapitulação) |
| Destruição de Konoha | 68–80 |
| Busca por Tsunade | 81–100 (sem o 97, filler) |
| Resgate do Sasuke | 107–135 |

Ficam de fora os fillers 97, 101–106 e 136–220. São **127 episódios**. A situação de cada um está em [`dados/episodios/`](dados/episodios/).

## Requisitos

- [Node.js](https://nodejs.org/) 20+ (gera e valida o complemento)
- [Python](https://www.python.org/) 3.10+ e `pip install -r requirements.txt`
- [FFmpeg](https://ffmpeg.org/) 6+ no `PATH`. Placa NVIDIA acelera a montagem (NVENC); sem ela, use `"codificador": "libx264"`.

## Uso rápido

```bash
cp config.exemplo.json config.local.json   # aponte a pasta dos episódios dublados
python -m ferramentas limpar               # detecta o que cortar nos 127 episódios
python -m ferramentas montar               # gera os MP4 e registra os links
python -m ferramentas servir               # deixa os vídeos disponíveis para a TV
npm test && git add dados && git commit -m "Episódios" && git push
```

Passo a passo completo e ajustes manuais: [docs/FLUXO_DE_TRABALHO.md](docs/FLUXO_DE_TRABALHO.md).

## Estrutura

```text
naruto-kai-dub/
├── dados/
│   ├── serie.json              # nome, descrição, arte e arcos
│   ├── textos.json             # títulos e sinopses do catálogo (sem spoiler)
│   ├── classico.json           # referência: dados da Wikipédia e miniaturas dos 220 episódios
│   └── episodios/s01eNNN.json  # um por episódio: o que é cortado e o link do vídeo
├── ferramentas/                # Python + FFmpeg: limpeza, montagem, servidor (e modo Kai)
├── scripts/                    # geração do complemento, teste local, importação de metadados
├── site/index.html             # página de instalação
├── tests/                      # testes com mídia sintética
├── docs/                       # arquitetura e fluxo de trabalho
└── .github/workflows/          # validação, testes e publicação automáticos
```

## Documentação

- [Fluxo de trabalho](docs/FLUXO_DE_TRABALHO.md)
- [Arquitetura](docs/ARQUITETURA.md)

## Créditos

- Ideia de complemento estático no GitHub: [Naruto Kai Stremio Addon](https://github.com/cybr23/Naruto-Kai-Stremio-Addon), de cybr23. Aquele repositório não tem licença, então nenhum código ou imagem dele foi copiado.
- Títulos e sinopses do catálogo: próprios, curtos e sem spoiler (`dados/textos.json`). A sinopse de cada episódio é um "Antes:" que resume o episódio anterior.
- Referência de conteúdo: [Wikipédia em português](https://pt.wikipedia.org/wiki/Lista_de_epis%C3%B3dios_de_Naruto), licença [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.pt-br); `dados/classico.json` guarda esse material e segue essa licença.
- Pôster, fundo, logo e miniaturas: servidos pelo próprio Stremio (Cinemeta/metahub), não armazenados aqui.

## Licença

Código sob a [licença MIT](LICENSE).
