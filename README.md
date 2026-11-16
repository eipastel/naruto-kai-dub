<p align="center"><img src="assets/logo.png" alt="Naruto Kai Dublado" width="420"></p>

<p align="center">
  <a href="https://github.com/eipastel/naruto-kai-dub/actions/workflows/publicar.yml"><img src="https://github.com/eipastel/naruto-kai-dub/actions/workflows/publicar.yml/badge.svg" alt="Validar e publicar"></a>
  <img src="https://img.shields.io/badge/Stremio-complemento-7b5bf5" alt="Stremio">
  <img src="https://img.shields.io/badge/idioma-PT--BR-009c3b" alt="PT-BR">
  <img src="https://img.shields.io/badge/licen%C3%A7a-MIT-blue" alt="MIT">
</p>

# Naruto Kai Dublado

Complemento (addon) para o **Stremio** com o **Naruto Kai** — a história de Naruto sem fillers e sem enrolação — usando a **dublagem brasileira**. Funciona no computador, no celular e nas **Smart TVs LG** (webOS).

O projeto tem duas partes:

1. **O complemento Stremio**: arquivos JSON estáticos publicados no GitHub Pages. Para mudar títulos, sinopses ou links, basta editar os dados e fazer `git push`; o Stremio passa a mostrar a novidade **sem reinstalar**.
2. **As ferramentas de dublagem** (Python + FFmpeg): encontram os cortes do Naruto Kai, descobrem de qual episódio original veio cada trecho e montam automaticamente a faixa dublada em PT-BR, com espaço para ajustes manuais.

> **Aviso legal.** Este repositório **não contém nem distribui vídeos ou áudios**. As ferramentas trabalham só com arquivos locais que você já possui, e o complemento só aponta para fontes que você mesmo configurar. Naruto pertence a Masashi Kishimoto, Shueisha, Studio Pierrot e licenciadores.

## Instalação no Stremio

Endereço do complemento:

```text
https://eipastel.github.io/naruto-kai-dub/manifest.json
```

- **Computador/celular:** abra <https://eipastel.github.io/naruto-kai-dub/> e clique em **Instalar no Stremio**, ou cole o endereço acima na busca de complementos.
- **TV LG:** no Stremio da TV, vá em *Complementos*, cole o endereço na busca e confirme. Outra opção: instale no computador com a mesma conta, que a TV sincroniza sozinha.

## Episódios

| Episódio | Título | Capítulos | Situação |
|---|---|---|---|
| T1E01 | Naruto Uzumaki! | 1–7 | Estrutura pronta; aguardando mapa e fonte de vídeo |

A situação de cada episódio vive em [`dados/episodios/`](dados/episodios/).

## Requisitos

- [Node.js](https://nodejs.org/) 20 ou mais novo (gera e valida o complemento)
- [Python](https://www.python.org/) 3.10 ou mais novo + `pip install -r requirements.txt`
- [FFmpeg](https://ffmpeg.org/) 6 ou mais novo no `PATH` (`ffmpeg` e `ffprobe`)

## Uso rápido

```bash
# 1. Configure os caminhos dos seus arquivos locais
cp config.exemplo.json config.local.json   # depois edite os caminhos

# 2. Mapeie o episódio 1 do Kai nos episódios originais dublados
python -m ferramentas mapear 1

# 3. Gere o MP4 com a dublagem brasileira
python -m ferramentas sincronizar 1

# 4. (Opcional) Sirva os MP4 na rede local para a TV
python -m ferramentas servir

# 5. Valide e gere o complemento
npm test
npm run build
```

O passo a passo completo, incluindo como ajustar a sincronia à mão e como adicionar novos episódios, está em [docs/FLUXO_DE_TRABALHO.md](docs/FLUXO_DE_TRABALHO.md).

## Estrutura

```text
naruto-kai-dub/
├── dados/
│   ├── serie.json              # nome, descrição e gêneros da série
│   └── episodios/s01e001.json  # um arquivo por episódio: metadados, mapa e links
├── ferramentas/                # Python + FFmpeg: cortes, mapeamento, sincronia, servidor
├── scripts/
│   ├── build.mjs               # valida os dados e gera o complemento em dist/
│   └── servir-addon.mjs        # testa o complemento localmente no Stremio
├── site/index.html             # página de instalação
├── assets/                     # pôster, fundo e logo (arte original do projeto)
├── tests/                      # testes de ponta a ponta com mídia sintética
├── docs/                       # arquitetura e fluxo de trabalho
└── .github/workflows/          # validação, testes e publicação automáticos
```

## Documentação

- [Fluxo de trabalho](docs/FLUXO_DE_TRABALHO.md): do arquivo local ao episódio no Stremio.
- [Arquitetura](docs/ARQUITETURA.md): como o complemento e as ferramentas funcionam por dentro.

## Créditos

A ideia de um complemento estático hospedado no GitHub veio do projeto [Naruto Kai Stremio Addon](https://github.com/cybr23/Naruto-Kai-Stremio-Addon), de cybr23. Aquele repositório não declara licença, então **nenhum código ou imagem dele foi copiado**: este é um projeto independente, escrito do zero.

## Licença

Código e arte original sob a [licença MIT](LICENSE).
