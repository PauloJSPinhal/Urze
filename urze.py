#!/usr/bin/env python3
# ============================================
# Projeto : urze
# Ficheiro: urze.py — gerador de esqueleto de projetos Python desktop (GTK3/Debian)
# Autor   : PauloJSPinhal
# Criado  : 2026-10-31
# GitHub  : https://github.com/PauloJSPinhal
# ============================================
"""urze — enraíza a estrutura completa de um projeto Python desktop.

Cria, num único comando, a estrutura universal: src layout, pyproject.toml
(hatchling), instalador em 4 fases (apt → venv → pip → verificação),
app de exemplo GTK3 com tematização completa, testes, metadados AppStream
e empacotamento Debian.

Uso:
    python3 urze.py <nome> [opções]
    python3 urze.py                    # interativo: pergunta o que faltar
    python3 urze.py meu-app --desc "Uma aplicação GTK"

Opções:
    --desc "texto"         descrição curta (ou caminho para um ficheiro de texto)
    --desc-file FICHEIRO   lê a descrição do projeto a partir de um ficheiro de texto
    --nome-visivel "X"     nome apresentável (omissão: derivado do nome)
    --autor "NOME"         autor dos cabeçalhos (omissão: PauloJSPinhal)
    --github URL           endereço GitHub (omissão: https://github.com/PauloJSPinhal)
    --dest DIR             diretório onde criar <nome>/ (omissão: '.')
    -y, --sem-interativo   nunca perguntar; usa as omissões (para scripts/CI)

Stdlib-only: corre num Debian nu com python3 apenas.
Cada ficheiro gerado recebe um cabeçalho que o identifica, caracteriza e
descreve o papel que desempenha no projeto.
"""

import argparse
import datetime
import keyword
import re
import sys
import xml.sax.saxutils
from dataclasses import dataclass, field
from pathlib import Path

# ------------------------------------------------------------------
# Valores por omissão para cabeçalhos e metadados.
# ------------------------------------------------------------------
AUTOR_PADRAO = "PauloJSPinhal"
GITHUB_PADRAO = "https://github.com/PauloJSPinhal"


# ------------------------------------------------------------------
# Contexto do projeto a gerar
# ------------------------------------------------------------------
# [MELHORIA] Antes, estes dados viviam em variáveis globais mutáveis
# (DIST, PKG, APPID, TOKENS, etc.) modificadas com `global` em main().
# Agrupar tudo numa dataclass elimina o estado global, torna o fluxo de
# dados explícito e permite testar ou invocar a geração várias vezes.
@dataclass
class ContextoProjeto:
    """Guarda todos os metadados normalizados e o mapa de tokens do projeto."""

    pasta: str                             # Nome da pasta do projeto (mantém maiúsculas: ex. OpenDWFx)
    dist: str                              # Nome PyPI/Debian em minúsculas:   opendwfx / meu-app
    pkg: str                               # Nome de import Python, com _:     opendwfx / meu_app
    appid: str                             # ID D-Bus/GTK (3 segmentos):       pt.paulojspinhal.opendwfx
    classe: str                            # Prefixo CamelCase para classes:   OpenDWFx / MeuApp
    visivel: str                           # Nome legível para humanos:        OpenDWFx / Meu App
    desc: str                              # Descrição curta sanitizada (1 linha)
    desc_longa: str = ""                   # Descrição longa (vinda de ficheiro de texto, se usado)
    autor: str = AUTOR_PADRAO              # Nome do autor nos cabeçalhos
    github: str = GITHUB_PADRAO            # URL base do GitHub do autor
    data: str = field(default_factory=lambda: datetime.date.today().isoformat())
    nao_interativo: bool = False           # Modo -y (sem perguntas)
    politica_existentes: str | None = None # None | "escrever_todos" | "ignorar_todos"
    tokens: dict[str, str] = field(init=False)

    def __post_init__(self) -> None:
        """Constrói o dicionário de substituição textual para os templates.

        [MELHORIA] Incluímos variantes escapadas para XML/Pango Markup
        (__DESC_XML__, __VISIVEL_XML__, __AUTOR_XML__) e __DESC_LONGA__
        para quando a descrição é carregada de um ficheiro de texto.
        """
        apresentacao = (
            self.desc_longa.strip()
            or "*(Escreve aqui uma breve apresentação do que o teu programa faz e para quem serve.)*"
        )
        self.tokens = {
            "__PASTA__": self.pasta,
            "__DIST__": self.dist,
            "__PKG__": self.pkg,
            "__APPID__": self.appid,
            "__CLASSE__": self.classe,
            "__VISIVEL__": self.visivel,
            "__DESC__": self.desc,
            "__DESC_LONGA__": apresentacao,
            "__AUTOR__": self.autor,
            "__GITHUB__": self.github,
            "__DATA__": self.data,
            "__DESC_XML__": xml.sax.saxutils.escape(self.desc),
            "__VISIVEL_XML__": xml.sax.saxutils.escape(self.visivel),
            "__AUTOR_XML__": xml.sax.saxutils.escape(self.autor),
        }


# ------------------------------------------------------------------
# Funções auxiliares de texto, cabeçalhos e validação de nomes
# ------------------------------------------------------------------


def subst(texto: str, ctx: ContextoProjeto) -> str:
    """Aplica todos os tokens do contexto ao texto de um template.

    [MELHORIA] Em vez de um ciclo `for chave, valor in TOKENS: texto.replace(...)`
    (que fazia substituições em cascata se o texto introduzido pelo utilizador
    contivesse acidentalmente o nome de outro token), compilamos uma expressão
    regular única e substituímos todos os tokens numa só passagem.
    """
    padrao = re.compile("|".join(re.escape(k) for k in ctx.tokens))
    return padrao.sub(lambda m: ctx.tokens[m.group(0)], texto)


def cabec(ctx: ContextoProjeto, ficheiro: str, papel: str, estilo: str = "#") -> str:
    """Gera o bloco de cabeçalho em caixa, comum a todos os ficheiros gerados.

    Identifica (projeto, ficheiro), caracteriza (autor, data, github) e
    situa o ficheiro (papel) na estrutura do projeto.
    Adapta a sintaxe de comentário ao tipo de ficheiro:
      - '#'    : Python, Bash, TOML, .desktop, .gitignore
      - 'css'  : folhas de estilo /* ... */
      - 'html' : Markdown e XML <!-- ... -->
    """
    linhas = [
        f"Projeto : {ctx.dist}",
        f"Ficheiro: {ficheiro} — {papel}",
        f"Autor   : {ctx.autor}",
        f"Criado  : {ctx.data}",
        f"GitHub  : {ctx.github}",
    ]
    # Calcula a linha mais comprida para desenhar a barra '===' à medida.
    largura = max(len(x) for x in linhas)
    barra = "=" * largura

    if estilo == "#":
        return "".join(f"# {x}\n" for x in [barra, *linhas, barra])
    if estilo == "css":
        bloco = ["/* " + barra] + [f" * {x}" for x in linhas] + [" " + barra + " */"]
        return "\n".join(bloco) + "\n"
    if estilo == "html":
        bloco = ["<!-- " + barra] + [f"     {x}" for x in linhas] + ["     " + barra + " -->"]
        return "\n".join(bloco) + "\n"
    raise ValueError(f"estilo de cabeçalho desconhecido: {estilo}")


def perguntar(rotulo: str, omissao: str = "", nao_interativo: bool = False) -> str:
    """Pergunta interativa no terminal com valor por omissão (Enter aceita).

    Se estiver em modo não-interativo (-y) ou se o stdin não for um terminal
    (ex.: pipe ou CI), devolve imediatamente o valor por omissão sem bloquear.
    """
    if nao_interativo or not sys.stdin.isatty():
        return omissao
    sugestao = f" [{omissao}]" if omissao else ""
    try:
        resposta = input(f"{rotulo}{sugestao}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return omissao
    return resposta or omissao


def normalizar(bruto: str, nao_interativo: bool = False) -> tuple[str, str, str]:
    """Normaliza o nome do projeto para as três formas: (pasta, dist, pkg).

    Convenção:
      - `pasta` (diretório do projeto): permite maiúsculas, minúsculas, dígitos,
        traços e underscores (ex.: 'OpenDWFx', 'Meu-App').
      - `dist`  (pacote PyPI e pacote .deb): minúsculas e traços (ex.: 'opendwfx', 'meu-app').
      - `pkg`   (módulo de import Python em src/): minúsculas e underscores (ex.: 'opendwfx', 'meu_app').

    Valida se o nome começa por letra, não excede 40 caracteres e não colide
    com palavras reservadas da linguagem Python (ex.: 'class', 'import').
    """
    # Preserva maiúsculas no nome da pasta, convertendo apenas espaços em traços.
    pasta = re.sub(r"\s+", "-", bruto.strip())
    pasta = re.sub(r"-{2,}", "-", pasta).strip("-")

    # Para PyPI/Debian (dist), normaliza para minúsculas e traços.
    dist = re.sub(r"[\s_]+", "-", pasta.lower())
    dist = re.sub(r"-{2,}", "-", dist).strip("-")

    if not re.fullmatch(r"[A-Za-z]([A-Za-z0-9_-]*[A-Za-z0-9])?", pasta):
        sys.exit(
            f"urze: nome inválido: {bruto!r}\n"
            "  usa letras (maiúsculas ou minúsculas), dígitos, traços ou underscores, "
            "começando por letra (ex.: 'OpenDWFx' ou 'meu-app')."
        )
    pkg = dist.replace("-", "_")
    if keyword.iskeyword(pkg):
        sys.exit(f"urze: {pkg!r} é uma palavra reservada do Python; escolhe outro nome.")
    if len(pasta) > 40:
        sys.exit("urze: nome demasiado longo (máximo 40 caracteres).")

    # Só pede confirmação se o nome da pasta teve espaços/traços alterados
    # (não incomoda o utilizador apenas por usar maiúsculas como 'OpenDWFx').
    if pasta != bruto.strip() and not nao_interativo and sys.stdin.isatty():
        confirmado = perguntar(
            f"Nome da pasta ajustado: {bruto!r} → {pasta!r} (Enter confirma, ou escreve outro)",
            pasta,
            nao_interativo=nao_interativo,
        )
        if confirmado and confirmado != pasta:
            return normalizar(confirmado, nao_interativo=nao_interativo)
    return pasta, dist, pkg


def construir_appid(autor: str, pkg: str) -> str:
    """Constrói um Application ID válido para GTK/GLib/D-Bus e AppStream.

    [MELHORIA CRÍTICA] Antes o script gerava `pt.<dist>` (apenas 2 segmentos,
    1 ponto). A função `Gio.Application.id_is_valid()` do GLib exige:
      1. Pelo menos DOIS pontos (mínimo 3 segmentos: ex. `pt.autor.app`);
      2. Nenhum segmento pode começar por algarismo;
      3. Apenas letras ASCII, dígitos, '_' ou '-' (sendo '_' o mais seguro para D-Bus).
    Com apenas 1 ponto, `Gtk.Application(application_id=...)` abortava no arranque!
    """
    # Limpa o nome do autor para apenas letras e dígitos em minúsculas.
    slug_autor = re.sub(r"[^a-z0-9]", "", autor.lower())
    if not slug_autor or not slug_autor[0].isalpha():
        slug_autor = "app" + slug_autor
    return f"pt.{slug_autor}.{pkg}"


def sanitizar_texto_curto(texto: str, fallback: str) -> str:
    """Remove quebras de linha, espaços múltiplos e aspas duplas.

    [MELHORIA] Usado tanto em `DESC` como em `VISIVEL` e `AUTOR` para garantir
    que nenhum valor introduzido pelo utilizador fecha acidentalmente uma string
    literal (`"..."`) no código Python ou no `pyproject.toml` gerados.
    """
    limpo = re.sub(r"\s+", " ", texto.replace('"', "'").replace("\\", "/")).strip()
    return limpo or fallback


def carregar_descricao(
    desc_arg: str | None,
    desc_file_arg: str | None,
    omissao: str,
    visivel: str,
    nao_interativo: bool,
) -> tuple[str, str]:
    """Obtém a descrição curta (1 linha) e longa (opcional), suportando ficheiro de texto.

    Permite três formas de fornecer um ficheiro de texto com a descrição:
      1. `--desc-file caminho/para/descricao.txt`
      2. `--desc caminho/para/descricao.txt` (ou `@caminho/para/descricao.txt`)
      3. Escrever o caminho do ficheiro diretamente quando perguntado no terminal.

    Se o ficheiro tiver várias linhas:
      - a primeira linha não vazia (sem `#` inicial) torna-se a descrição curta (`desc`);
      - o texto completo do ficheiro torna-se a apresentação do `README.md` (`desc_longa`).
    """
    caminho_fich: Path | None = None

    if desc_file_arg:
        caminho_fich = Path(desc_file_arg).expanduser()
        if not caminho_fich.is_file():
            sys.exit(f"urze: ficheiro de descrição não encontrado: {desc_file_arg!r}")
        bruto = ""
    else:
        bruto = desc_arg or perguntar(
            "Descrição curta (ou caminho para ficheiro .txt/.md)",
            omissao,
            nao_interativo=nao_interativo,
        )
        candidato_str = bruto[1:].strip() if bruto.startswith("@") else bruto.strip()
        if candidato_str and "\n" not in candidato_str and len(candidato_str) < 260:
            try:
                candidato = Path(candidato_str).expanduser()
                if candidato.is_file():
                    caminho_fich = candidato
                elif bruto.startswith("@"):
                    sys.exit(f"urze: ficheiro de descrição não encontrado: {candidato_str!r}")
            except OSError:
                pass

    if caminho_fich is not None:
        try:
            conteudo = caminho_fich.read_text(encoding="utf-8").strip()
        except OSError as exc:
            sys.exit(f"urze: erro ao ler ficheiro de descrição {caminho_fich}: {exc}")
        linhas_brutas = conteudo.splitlines()
        primeira = ""
        indice_resto = 0
        for idx, ln in enumerate(linhas_brutas):
            limpa = ln.strip().lstrip("#").strip()
            if limpa:
                primeira = limpa
                indice_resto = idx + 1
                break
        desc_curta = sanitizar_texto_curto(primeira or omissao, visivel)
        corpo_extra = "\n".join(linhas_brutas[indice_resto:]).strip()
        return desc_curta, corpo_extra

    return sanitizar_texto_curto(bruto, visivel), ""


# ------------------------------------------------------------------
# TEMPLATES — ficheiros de topo do projeto gerado.
# Cada função `t_*()` devolve o corpo do ficheiro com marcadores
# (__DIST__, __PKG__, etc.). O cabeçalho em caixa é acrescentado
# automaticamente pela rotina `escrever()`.
# ------------------------------------------------------------------


def t_run() -> str:
    """Template do script `./run` na raiz do projeto gerado."""
    return '''\
#!/usr/bin/env bash
# Script de arranque em desenvolvimento: executa o pacote dentro do venv,
# nunca contra o Python do sistema. É o equivalente de `python -m __PKG__`
# com o ambiente certo garantido.
#
# Porquê `-m` e não `src/__PKG__/main.py`: o src layout exige que o pacote
# esteja importável (o install.py faz `pip install -e .` no venv); correr
# o ficheiro diretamente quebraria os imports relativos do pacote.
set -euo pipefail
cd "$(dirname "$0")"

PY=".venv/bin/python"
if [[ ! -x "$PY" ]]; then
    echo "Ambiente não configurado. Corre primeiro: ./install.sh (ou ./scripts/install.py)" >&2
    exit 1
fi

exec "$PY" -m __PKG__ "$@"
'''


def t_install_sh() -> str:
    """Template de `install.sh` na raiz do projeto gerado.

    Executa o instalador em 4 fases (`scripts/install.py`) e regista a
    aplicação no menu do utilizador (`~/.local/share/applications`), ícone
    (`~/.local/share/icons/hicolor/scalable/apps`) e comando (`~/.local/bin`).
    """
    return r'''\
#!/usr/bin/env bash
# Instalador completo da aplicação:
#   1. Corre `./scripts/install.py` (pacotes apt -> .venv -> pip -e . -> verificação)
#   2. Instala o comando em `~/.local/bin/__DIST__`
#   3. Instala o ícone e o atalho `.desktop` no menu de aplicações do utilizador
#
# Opções:
#   ./install.sh            -> instala ambiente + atalho no menu do utilizador
#   ./install.sh --dev      -> prepara apenas o ambiente de desenvolvimento (.venv)
#   ./install.sh --check    -> apenas verifica se o ambiente está pronto (CI)

set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

RAIZ="$PWD"
DIST="__DIST__"
APPID="__APPID__"

if [[ "${1:-}" == "--check" ]]; then
    exec ./scripts/install.py --check
fi

APENAS_DEV=false
if [[ "${1:-}" == "--dev" ]]; then
    APENAS_DEV=true
fi

echo "==> A configurar ambiente com ./scripts/install.py..."
./scripts/install.py

if [[ "$APENAS_DEV" == true ]]; then
    echo "  [ok]    Ambiente de desenvolvimento pronto. Corre: ./run"
    exit 0
fi

echo "==> A instalar atalho e comando no perfil do utilizador..."
BIN_DIR="${HOME}/.local/bin"
APPS_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"

mkdir -p "$BIN_DIR" "$APPS_DIR" "$ICON_DIR"

# Cria wrapper executável em ~/.local/bin/__DIST__ que invoca o .venv do projeto
cat > "${BIN_DIR}/${DIST}" <<FIM
#!/usr/bin/env bash
exec "${RAIZ}/run" "\$@"
FIM
chmod 755 "${BIN_DIR}/${DIST}"
echo "  [ok]    Comando instalado em: ${BIN_DIR}/${DIST}"

# Instala o ícone vetorial no tema hicolor do utilizador
if [[ -f "data/icons/scalable/apps/${APPID}.svg" ]]; then
    install -m 644 "data/icons/scalable/apps/${APPID}.svg" "${ICON_DIR}/${APPID}.svg"
    echo "  [ok]    Ícone instalado em: ${ICON_DIR}/${APPID}.svg"
fi

# Instala o lançador .desktop apontando para o comando instalado
if [[ -f "data/${APPID}.desktop" ]]; then
    sed "s|^Exec=.*|Exec=${BIN_DIR}/${DIST}|" "data/${APPID}.desktop" > "${APPS_DIR}/${APPID}.desktop"
    chmod 644 "${APPS_DIR}/${APPID}.desktop"
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
    fi
    echo "  [ok]    Atalho de menu instalado em: ${APPS_DIR}/${APPID}.desktop"
fi

echo
echo "Instalação concluída! Podes iniciar com './run' ou pelo menu de aplicações."
'''


def t_uninstall_sh() -> str:
    """Template de `uninstall.sh` na raiz do projeto gerado.

    Remove o comando, ícone, atalho do menu de aplicações e opcionalmente
    o ambiente virtual (`.venv`) e configurações do utilizador (`--purge`).
    """
    return r'''\
#!/usr/bin/env bash
# Desinstalador da aplicação:
# Remove o atalho do menu de aplicações, ícone, comando em ~/.local/bin e .venv.
#
# Opções:
#   ./uninstall.sh           -> remove atalho, ícone, comando e ambiente .venv
#   ./uninstall.sh --keep-venv -> remove apenas atalho, ícone e comando (mantém .venv)
#   ./uninstall.sh --purge   -> remove tudo incluindo configurações em ~/.config/__PKG__

set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

DIST="__DIST__"
PKG="__PKG__"
APPID="__APPID__"

MANTER_VENV=false
PURGAR_CONFIG=false

for arg in "$@"; do
    case "$arg" in
        --keep-venv)
            MANTER_VENV=true
            ;;
        --purge)
            PURGAR_CONFIG=true
            ;;
        -h|--help)
            echo "Utilização: ./uninstall.sh [--keep-venv] [--purge]"
            echo "  --keep-venv   Remove apenas os atalhos do utilizador, mantendo a pasta .venv"
            echo "  --purge       Remove também as preferências guardadas em ~/.config/${PKG}"
            exit 0
            ;;
        *)
            echo "Opção desconhecida: $arg" >&2
            exit 1
            ;;
    esac
done

BIN_FILE="${HOME}/.local/bin/${DIST}"
DESKTOP_FILE="${HOME}/.local/share/applications/${APPID}.desktop"
ICON_FILE="${HOME}/.local/share/icons/hicolor/scalable/apps/${APPID}.svg"
CONFIG_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/${PKG}"

for ficheiro in "$BIN_FILE" "$DESKTOP_FILE" "$ICON_FILE"; do
    if [[ -f "$ficheiro" || -L "$ficheiro" ]]; then
        rm -f "$ficheiro"
        echo "  [ok]    Removido: $ficheiro"
    fi
done

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${HOME}/.local/share/applications" >/dev/null 2>&1 || true
fi

if [[ "$MANTER_VENV" == false && -d ".venv" ]]; then
    rm -rf .venv
    echo "  [ok]    Ambiente virtual removido (.venv)"
fi

if [[ "$PURGAR_CONFIG" == true && -d "$CONFIG_DIR" ]]; then
    rm -rf "$CONFIG_DIR"
    echo "  [ok]    Configurações removidas ($CONFIG_DIR)"
fi

echo "  [ok]    Desinstalação concluída."
'''


def t_pyproject() -> str:
    """Template do `pyproject.toml` (PEP 621 + Hatchling)."""
    return '''\
# Fonte ÚNICA da verdade sobre o projeto: metadados, dependências Python,
# entry points e configuração das ferramentas (pytest, hatchling).
# As dependências de SISTEMA (Debian) ficam à parte, em requirements-apt.txt.
#
# A versão vive só em src/__PKG__/__init__.py (__version__); o hatchling
# extrai-a daí — não a repitas aqui.

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "__DIST__"
description = "__DESC__"
readme = "README.md"
requires-python = ">=3.9"
license = { text = "GPL-3.0-or-later" }
authors = [{ name = "__AUTOR__", url = "__GITHUB__" }]
keywords = ["gtk3", "desktop", "debian", "linux"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: X11 Applications :: GTK",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
    "Operating System :: POSIX :: Linux",
    "Programming Language :: Python :: 3",
    "Topic :: Desktop Environment",
]
dependencies = []          # dependências Python externas (pip), se aparecerem
dynamic = ["version"]

[project.optional-dependencies]
dev = ["pytest", "pytest-cov", "ruff", "mypy"]

[project.scripts]
# Entry point usado pelo .deb e por qualquer instalação `pip install .`:
__DIST__ = "__PKG__.main:main"

[project.urls]
Homepage = "__GITHUB__/__DIST__"

[tool.hatch.version]
path = "src/__PKG__/__init__.py"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"

[tool.hatch.build.targets.wheel]
packages = ["src/__PKG__"]
# dev-mode-dirs cria um ficheiro .pth direto para src/ durante `pip install -e .`,
# evitando que o hatchling exija o pacote externo `editables` (perfeito para
# funcionar com `--no-build-isolation` e melhor para autocompletar no IDE).
dev-mode-dirs = ["src"]
'''


def t_requirements() -> str:
    """Template do `requirements.txt` (opcional, para lock de versões pip)."""
    return '''\
# Ficheiro de bloqueio GERADO — não editar à mão.
#
# A fonte única das dependências Python é o pyproject.toml ([project]
# dependencies / [project.optional-dependencies]). Este ficheiro só existe
# para congelar versões exatas quando quiseres reprodutibilidade total.
#
# Regenerar:  .venv/bin/pip freeze > requirements.txt
# Restaurar:  .venv/bin/pip install -r requirements.txt
'''


def t_requirements_apt() -> str:
    """Template do `requirements-apt.txt` (dependências Debian do projeto).

    [MELHORIA] Adicionados `python3-pip` e `python3-hatchling` para que o
    `pip install --no-build-isolation -e .` funcione 100% com pacotes de
    sistema Debian, sem precisar de ir à internet descarregar o hatchling.
    """
    return '''\
# Dependências de SISTEMA (Debian/GNU Linux) do projeto.
#
# É a fonte única para três consumidores:
#   1. scripts/install.py        — verifica e instala o que falta (fase 1);
#   2. scripts/build_packages.sh — gera a linha Depends: do debian/control;
#   3. CI (--check)              — falha se algo faltar, sem instalar.
#
# Sintaxe à la debian/control:  nome-do-pacote (>= versão)  — a restrição
# de versão é opcional e validada pelo install.py com dpkg.
#
# Nota: em Flatpak esta lista é ignorada (as libs vêm do runtime);
# o install.py deteta FLATPAK_ID e salta a fase apt.

python3-venv            # cria o .venv — tem de vir antes da fase 2
python3-pip             # instalador pip dentro do venv
python3-hatchling       # backend de build (permite pip install --no-build-isolation)
python3-gi              # PyGObject: torna o GTK acessível como `import gi`
python3-gi-cairo        # ponte PyGObject ↔ cairo
gir1.2-gtk-3.0          # GTK3 (introspecção GObject)
gir1.2-gdkpixbuf-2.0    # carregamento de imagens
desktop-file-utils      # validação/instalação do lançador .desktop
'''


def t_gitignore() -> str:
    """Template do `.gitignore`."""
    return '''\
# Ignora artefactos locais: ambiente virtual, caches, builds e packaging.
.venv/

# Python
__pycache__/
*.py[cod]
*.egg-info/
build/
dist/

# Ferramentas de desenvolvimento
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/

# Empacotamento Debian, AppImage, Windows e macOS (gerados por scripts/build_*.sh)
debian/.debhelper/
debian/files
debian/*.log
debian/*.substvars
debian/debhelper-build-stamp
debian/__DIST__/
*.deb
*.changes
*.buildinfo
*.AppImage
AppDir/
*.spec
*.exe
*.iss
*.zip
*.dmg
*.icns
*.app/
'''


def t_readme() -> str:
    """Template do `README.md` na raiz — curto, para ir preenchendo ao longo do projeto."""
    return '''\
# __VISIVEL__

> __DESC__

__DESC_LONGA__

## Funcionalidades

- [ ] *(Funcionalidade 1)*
- [ ] *(Funcionalidade 2)*

## Instalação

```bash
./install.sh
```

Para desinstalar:

```bash
./uninstall.sh
```

## Como Usar

```bash
./run
```

## Ajuda para Programar neste Projeto

Se tens dúvidas sobre como este esqueleto funciona ou onde deves escrever o teu código, consulta os guias passo a passo na pasta **[`docs/`](docs/)**.

## Licença

Distribuído sob a licença GPL-3.0-or-later. Consulta [LICENSE.md](LICENSE.md).  
Autor: **__AUTOR__** (__GITHUB__)
'''


def t_architecture() -> str:
    """Template do `ARCHITECTURE.md` na raiz — esqueleto curto para documentar a app à medida que cresce."""
    return '''\
# Arquitetura do Projeto — __VISIVEL__

> **Dica:** Para perceberes como funciona a estrutura base criada pelo `urze` e onde escrever cada parte do código, lê os guias simples na pasta **[`docs/`](docs/)**.
> Usa este ficheiro apenas para ires anotando o que a **tua** aplicação faz à medida que cresce.

## Visão Geral

*(Descreve aqui, em poucas linhas, como funciona o teu programa.)*

## Módulos da Aplicação (`src/__PKG__/modules/`)

| Módulo | O que faz |
| :--- | :--- |
| `appearance` | Muda as cores (sistema/claro/escuro) e o tipo de letra da janela |
| *(novo módulo)* | *(Descreve o que faz quando o criares)* |

## Janelas e Ecrãs (`src/__PKG__/views/`)

| Ficheiro | Janela / Ecrã |
| :--- | :--- |
| `main.py` | Janela principal da aplicação |
| *(nova vista)* | *(Descreve o ecrã ou caixa de diálogo quando a criares)* |
'''


def t_changelog() -> str:
    """Template do `CHANGELOG.md` na raiz — esqueleto curto para registar versões."""
    return '''\
# Registo de Alterações (Changelog)

Todas as alterações importantes do **__VISIVEL__** são anotadas aqui.

## [Não Lançado]

### Adicionado
- 

### Alterado
- 

### Corrigido
- 

## [0.1.0] - __DATA__

### Adicionado
- Criação inicial do projeto.
'''


def t_contributing() -> str:
    """Template do `CONTRIBUTING.md` na raiz — esqueleto curto para colaboradores."""
    return '''\
# Como Contribuir — __VISIVEL__

## Preparar o Ambiente

```bash
./scripts/install.py
```

## Correr o Programa

```bash
./run
```

## Correr os Testes

```bash
.venv/bin/python -m pytest -q
```

## Regras do Projeto

- *(Acrescenta aqui as tuas notas ou regras para quem quiser ajudar no projeto.)*
'''


def t_security() -> str:
    """Template do `SECURITY.md` na raiz — esqueleto curto de política de segurança."""
    return '''\
# Política de Segurança — __VISIVEL__

## Versões Suportadas

| Versão | Suportada |
| :--- | :--- |
| `0.1.x` | Sim |

## Como Comunicar um Problema de Segurança

Se encontrares uma falha de segurança, por favor contacta diretamente **__AUTOR__** através de __GITHUB__/__DIST__/issues (ou em privado no GitHub) descrevendo como reproduzir o problema.
'''


# ------------------------------------------------------------------
# TEMPLATES — docs/ (Guias de ajuda em linguagem simples para iniciantes).
# ------------------------------------------------------------------


def t_doc_pastas_e_ficheiros() -> str:
    """Guia 1 em `docs/`: explica cada pasta e ficheiro sem jargão técnico."""
    return '''\
# 1. Para que serve cada pasta e ficheiro

Quando olhas para o projeto pela primeira vez, vês muitas pastas e ficheiros. Não te assustes: **90% do teu tempo vais mexer apenas dentro da pasta `src/__PKG__/`**. Tudo o resto está lá para trabalhar por ti nos bastidores.

Aqui está a explicação simples de cada peça:

---

## Na pasta principal (Raiz)

- **`install.sh`** — Instala tudo: prepara o ambiente (`.venv`) e cria o atalho do programa no menu de aplicações do teu computador.
- **`uninstall.sh`** — Desinstala o atalho do menu, o comando e limpa o ambiente virtual (`.venv`).
- **`run`** — É o botão de ligar do teu programa enquanto estás a programar. Escreves `./run` no terminal e a tua janela abre.
- **`pyproject.toml`** — É o "bilhete de identidade" do projeto. Diz o nome do programa (`__DIST__`), quem é o autor e que bibliotecas de Python ele usa.
- **`requirements-apt.txt`** — É a "lista de compras" para o sistema Linux (Debian/Ubuntu). Tem os nomes das peças que o próprio Linux precisa de ter instaladas para conseguir desenhar janelas no ecrã.
- **`requirements.txt`** — Vem vazio. Só serve se um dia quiseres anotar versões exatas de bibliotecas extra.
- **`README.md`, `CHANGELOG.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE.md`** — Ficheiros de texto na raiz para ires preenchendo com informações sobre o teu programa à medida que o vais desenvolvendo.

---

## Pasta `src/__PKG__/` (Onde vive o teu programa!)

É aqui dentro que está todo o código Python da tua aplicação:

- **`__init__.py`** — Diz ao Python que esta pasta é um programa e guarda o número da versão (ex.: `__version__ = "0.1.0"`). **Nota:** tem mesmo de ter dois traços (`__`) de cada lado do nome!
- **`__main__.py`** — Serve apenas de ponte: quando corres `./run`, o Python passa por aqui e salta logo para o `main.py`. Não precisas de mexer nele.
- **`main.py`** — **Começa por aqui!** É onde está desenhada a janela inicial que vês quando abres o programa.
- **`defaults/`** — Guarda as opções e as cores padrão do programa:
  - `config.py`: Lê e grava as escolhas do utilizador (como o tema escuro ou claro) num ficheiro na pasta pessoal (`~/.config/__PKG__/aparencia.json`).
  - `tema_escuro.css` e `tema_claro.css`: Ficheiros com as cores da janela.
- **`modules/`** — É a pasta do **"cérebro"** do programa. Aqui colocas as funções que fazem contas, tratam de textos, guardam ficheiros ou ligam à internet. Já traz a pasta `appearance/` feita, que serve para mudar o tema de cores e o tipo de letra.
- **`views/`** — É a pasta do **"rosto"** do programa. Quando o teu programa tiver mais janelas ou caixas de aviso, é aqui que as vais criar.
- **`core/`** — Tem um modelo base (`ModuloBase`) para ajudar a organizar os teus módulos sempre da mesma maneira.

---

## As outras pastas de apoio

- **`scripts/`** — Tem cinco ajudantes automáticos:
  - `install.py`: Prepara o teu computador Linux todo sozinho para o programa funcionar (é chamado automaticamente pelo `./install.sh`).
  - `build_packages.sh`: Cria um instalador `.deb` (para Debian, Ubuntu e Linux Mint).
  - `build_appimage.sh`: Cria um ficheiro `.AppImage` portátil (funciona em qualquer Linux sem instalar).
  - `build_windows.sh`: Cria a pasta executável (`.exe`) e o instalador para Windows (usando MSYS2 + PyInstaller + Inno Setup).
  - `build_macos.sh`: Cria a aplicação `.app` e o instalador `.dmg` para computadores Apple (macOS).
- **`.github/workflows/build.yml`** — Se colocares o projeto no GitHub, este ficheiro faz com que os computadores gratuitos do GitHub criem sozinhos os instaladores de Linux (`.deb` e `.AppImage`), Windows (`.exe`) e Apple macOS (`.dmg`) para ti!
- **`data/`** — Tem o ícone do programa (`icons/`) e o atalho (`__APPID__.desktop`) para que o programa apareça no menu "Aplicações" do teu computador quando for instalado.
- **`tests/`** — Serve para colocar pequenos testes automáticos que verificam se o teu código não tem erros básicos.
- **`docs/`** — Esta pasta onde estás agora! Contém estes guias de ajuda e o ficheiro `notas.md` para apontares as tuas ideias.
'''


def t_doc_instalador_e_arranque() -> str:
    """Guia 2 em `docs/`: explica como funciona o install.sh / install.py e o ./run."""
    return '''\
# 2. Como funciona o instalador e o arranque

Para que uma aplicação gráfica em Python funcione sem dar dores de cabeça, o projeto traz três scripts prontos na pasta principal:
- **`./install.sh`** — Instala tudo (ambiente + atalho no menu de aplicações).
- **`./run`** — Abre o programa imediatamente enquanto estás a programar.
- **`./uninstall.sh`** — Remove o atalho do menu e limpa o ambiente se quiseres desinstalar.

Veja de forma simples o que cada um faz nos bastidores.

---

## O que acontece quando corres `./install.sh` (ou `./scripts/install.py`)?

O `./install.sh` chama primeiro o `./scripts/install.py`, que prepara o terreno em **4 passos automáticos**:

### Passo 1: Instalar peças do Linux (`apt`)
Lê a lista `requirements-apt.txt` e vê se falta alguma peça no teu computador (por exemplo, o motor gráfico GTK3). Se faltar alguma, pede a tua palavra-passe (`sudo`) uma única vez e instala tudo. Se já tiveres tudo, avança logo.

### Passo 2: Criar uma "caixa isolada" (`.venv`)
Cria uma pasta oculta chamada `.venv`. Pensa nela como uma oficina privada só para este projeto: o que instalares ali dentro não estraga nada no resto do teu computador, mas consegue ver o motor gráfico do sistema.

### Passo 3: Ligar o teu código (`pip`)
Regista a pasta `src/__PKG__/` dentro dessa oficina `.venv`. Faz isto de uma forma especial ("modo editável"): sempre que mudares uma linha no teu código e guardares o ficheiro, a mudança fica logo ativa sem precisares de voltar a correr o instalador!

### Passo 4: Teste final e atalho no menu
Confirma que não faltam peças e que o Python já consegue abrir janelas GTK3. De seguida, o `./install.sh` copia o ícone e o atalho para a tua pasta pessoal (`~/.local/share/applications`), para que o programa apareça logo no menu de aplicações do computador.

---

## O que acontece quando corres `./run`?

Quando escreves `./run` no terminal, acontece esta viagem em menos de um segundo:

1. O `run` chama o Python que está dentro da oficina `.venv` e pede-lhe para abrir a pasta `src/__PKG__/`.
2. O Python entra por `src/__PKG__/__main__.py`, que chama a função `main()` dentro de `src/__PKG__/main.py`.
3. O `main.py` lê as preferências guardadas do utilizador (que cor e que letra escolheu da última vez) usando o `defaults/config.py`.
4. O `main.py` desenha a janela no ecrã, aplica as cores através da pasta `modules/appearance/` e fica à espera que cliques num botão!
'''


def t_doc_onde_escrever_codigo() -> str:
    """Guia 3 em `docs/`: guia prático passo a passo de onde programar."""
    return '''\
# 3. Onde escrever o teu código (Guia passo a passo)

Quando começares a criar a tua aplicação, o segredo para não te perderes é separar o código em dois sítios:

1. **A lógica (as contas, ler ficheiros, processar dados)** vai para `src/__PKG__/modules/`.
2. **O visual (janelas, botões, caixas de texto)** vai para `src/__PKG__/main.py` e `src/__PKG__/views/`.

Abaixo tens exemplos práticos prontos a copiar.

---

## Caso 1: Quero criar uma função nova (Lógica)

Imagina que estás a fazer um programa que calcula descontos ou trata de um texto. Não coloques as contas misturadas com o código dos botões!

**Passo 1:** Cria uma pasta nova dentro de `src/__PKG__/modules/`, por exemplo:
`src/__PKG__/modules/calculadora/`

**Passo 2:** Cria lá dentro um ficheiro `__init__.py` (com dois traços de cada lado) com a tua função:

```python
# Ficheiro: src/__PKG__/modules/calculadora/__init__.py

def somar_valores(a: float, b: float) -> float:
    """Soma dois números e devolve o resultado."""
    return a + b
```

**Passo 3:** Agora, na tua janela (`src/__PKG__/main.py`), só tens de importar e usar:

```python
from .modules.calculadora import somar_valores

resultado = somar_valores(10, 5)
print(resultado)
```

---

## Caso 2: Quero mexer na janela principal

No início do projeto, podes desenhar os teus botões e caixas de texto diretamente no ficheiro **`src/__PKG__/main.py`**, dentro da classe `Janela`.

Repara na zona que diz `# --- área de demonstração ---` dentro do `main.py`: podes apagar o botão, o campo de texto e o interruptor de exemplo que lá estão e colocar os teus próprios botões!

---

## Caso 3: O `main.py` está a ficar grande e quero outra janela

Quando quiseres abrir uma segunda janela (por exemplo, uma janela de "Sobre" ou "Definições"), coloca-a na pasta **`src/__PKG__/views/`**.

**Passo 1:** Cria o ficheiro `src/__PKG__/views/janela_sobre.py`:

```python
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ..modules.appearance import aplicar_tema


class JanelaSobre(Gtk.Dialog):
    def __init__(self, janela_mae, config):
        super().__init__(title="Sobre", transient_for=janela_mae, flags=0)
        self.add_buttons("Fechar", Gtk.ResponseType.CLOSE)
        self.set_default_size(320, 150)

        caixa = self.get_content_area()
        caixa.pack_start(Gtk.Label(label="__VISIVEL__ — Criado por __AUTOR__"), True, True, 10)

        # Aplica o mesmo tema (claro/escuro) e letra da janela principal
        aplicar_tema(self, config)
        self.show_all()
```

**Passo 2:** No `src/__PKG__/main.py`, importa e abre essa janela quando um botão for clicado:

```python
from .views.janela_sobre import JanelaSobre

# Dentro de uma função de clique dum botão na Janela:
dialogo = JanelaSobre(self, self.config)
dialogo.run()
dialogo.destroy()
```

---

## Caso 4: Quero guardar uma preferência do utilizador

Se quiseres que o programa se lembre de alguma escolha quando fecha e volta a abrir (por exemplo, o nome do utilizador):

1. Abre `src/__PKG__/defaults/config.py`.
2. Na classe `ConfigAparencia`, acrescenta a tua linha (ex.: `nome_utilizador: str = ""`).
3. Na função `carregar_config()`, acrescenta a leitura desse campo.
4. Sempre que chamares `guardar_config(self.config)`, essa informação fica gravada automaticamente!
'''


def t_doc_cores_letra_e_icone() -> str:
    """Guia 4 em `docs/`: como personalizar o aspeto visual e o ícone."""
    return '''\
# 4. Como mudar cores, tipo de letra e ícone

O teu projeto já traz um sistema pronto para mudar entre tema claro, tema escuro e tema do sistema, além de um ícone de exemplo. Veja como personalizar tudo ao teu gosto.

---

## 1. Mudar as cores dos temas (Claro e Escuro)

As cores não estão escondidas no meio do código Python; estão em dois ficheiros fáceis de editar na pasta **`src/__PKG__/defaults/`**:

- **`tema_escuro.css`** — Cores usadas quando o utilizador escolhe o esquema **Preto**.
- **`tema_claro.css`** — Cores usadas quando o utilizador escolhe o esquema **Branco**.

Podes abrir qualquer um deles num editor de texto e mudar os códigos das cores (por exemplo, `#1e2027`). Guarda o ficheiro, corre `./run` e vês logo as cores novas!

---

## 2. Mudar o tipo de letra inicial

No ficheiro `src/__PKG__/main.py`, procura a linha:

```python
self.botao_fonte.set_font(config.fonte or "Noto Sans 11")
```

Se quiseres outro tamanho ou tipo de letra inicial (quando o utilizador ainda não escolheu nenhum), basta trocar `"Noto Sans 11"` por outro nome, como `"Sans 12"` ou `"Ubuntu 11"`.

---

## 3. Trocar o ícone da aplicação

O programa já traz um ícone de exemplo criado em:
**`data/icons/scalable/apps/__APPID__.svg`**

Para colocares o teu próprio ícone:

1. Cria ou descarrega um ícone em formato **`.svg`** (por exemplo, usando o programa gratuito Inkscape).
2. Guarda-o por cima desse ficheiro com o mesmo nome: `data/icons/scalable/apps/__APPID__.svg`.

Como tem o mesmo nome e já está no sítio certo, não precisas de mudar mais nada no código!
'''


def t_doc_extras_e_deb() -> str:
    """Guia 5 em `docs/`: como instalar pacotes extra e criar instaladores (.deb, AppImage, Windows e macOS)."""
    return '''\
# 5. Como adicionar bibliotecas extra e criar instaladores (`Linux`, `Windows` e `macOS`)

À medida que o teu programa cresce, podes precisar de usar bibliotecas novas ou podes querer partilhar o programa com outras pessoas em Linux, Windows ou computadores Apple (Mac).

---

## 1. Quando precisares de uma biblioteca nova

Há dois lugares onde podes acrescentar ferramentas novas, dependendo do tipo de biblioteca:

### A) Se for uma ferramenta do sistema Linux (Debian/Ubuntu)
Por exemplo, um pacote que começa por `python3-...` ou `gir1.2-...`:
1. Abre o ficheiro **`requirements-apt.txt`** na raiz do projeto.
2. Escreve o nome do pacote numa linha nova.
3. Corre `./scripts/install.py` no terminal.

### B) Se for uma biblioteca de Python normal (`pip`)
Por exemplo, `requests` ou `pillow`:
1. Abre o ficheiro **`pyproject.toml`** na raiz do projeto.
2. Procura a linha `dependencies = []` e coloca o nome lá dentro, assim:
   ```toml
   dependencies = ["requests"]
   ```
3. Corre `./scripts/install.py` no terminal.

---

## 2. Como criar um instalador `.deb` (Debian, Ubuntu, Linux Mint)

Para instalares o programa como uma aplicação oficial do sistema (que aparece no menu de aplicações):

1. Abre o terminal na pasta do projeto e corre:
   ```bash
   ./scripts/build_packages.sh
   ```
2. Ele cria um ficheiro **`.deb`** na pasta imediatamente acima da pasta do teu projeto.
3. Para instalar no computador:
   ```bash
   sudo apt install ../__DIST___*.deb
   ```

---

## 3. Como criar um `.AppImage` (Qualquer distribuição Linux)

O formato **AppImage** é um único ficheiro portátil: quem o recebe só precisa de clicar duas vezes nele para abrir o programa, sem instalar nada.

1. Abre o terminal na pasta do projeto e corre:
   ```bash
   ./scripts/build_appimage.sh
   ```
2. O script monta a estrutura `AppDir`, descarrega a ferramenta `appimagetool` (se ainda não a tiveres) e cria o ficheiro **`../__DIST__-<versão>-x86_64.AppImage`**.

---

## 4. Como criar o Executável e Instalador para Windows (`.exe`)

O projeto cria a versão Windows em **Modo Pasta (`--onedir`) + Instalador (`Setup.exe`)**, para que o programa abra instantaneamente no Windows. Tens duas formas de o gerar:

### Forma A: Automática pelo GitHub (Sem precisares de ter Windows!)
1. Cria um repositório no GitHub e envia para lá o teu projeto (`git push`).
2. O ficheiro **`.github/workflows/build.yml`** (que já vem pronto no projeto) entra em ação sozinho nos servidores do GitHub.
3. Vai à página do teu projeto no GitHub → separador **Actions** → clica na última execução e descarrega o ficheiro **`instaladores-windows`** (traz o instalador `Setup-__DIST__.exe` e o `.zip` portátil)!

### Forma B: Num computador (ou Máquina Virtual) com Windows
1. No Windows, instala o **MSYS2** (https://www.msys2.org/) e opcionalmente o **Inno Setup** (https://jrsoftware.org/isinfo.php).
2. Abre o terminal **MSYS2 MINGW64**, entra na pasta do teu projeto e corre:
   ```bash
   ./scripts/build_windows.sh
   ```
3. O script instala o Python + GTK3 para Windows, gera a pasta executável em `dist/__DIST__/`, cria um `.zip` portátil e (se o Inno Setup estiver instalado) cria o instalador **`dist/Setup-__DIST__-<versão>.exe`**!

---

## 5. Como criar o Instalador para Apple macOS (`.app` e `.dmg`)

Nos computadores Apple, os programas vêm dentro de um ficheiro **`.dmg`** com a aplicação **`.app`** lá dentro (pronta para arrastar para a pasta *Aplicações*). Também tens duas formas de o criar:

### Forma A: Automática pelo GitHub (Sem precisares de ter um Mac!)
1. Quando envias o código para o GitHub (`git push`), o mesmo ficheiro **`.github/workflows/build.yml`** liga gratuitamente uma máquina Apple nos servidores do GitHub.
2. Vai ao separador **Actions** do teu GitHub e descarrega o ficheiro **`instaladores-macos`** (contém o `dist/__DIST__-<versão>-macos.dmg`)!

### Forma B: Num computador Apple (Mac)
1. Com o **Homebrew** instalado (https://brew.sh/), abre o Terminal na pasta do projeto e corre:
   ```bash
   ./scripts/build_macos.sh
   ```
2. O script instala o GTK3 via Homebrew, cria a aplicação `dist/__DIST__.app` e empacota tudo no instalador **`dist/__DIST__-<versão>-macos.dmg`**.

> **Nota para utilizadores de Mac:** Como o instalador é criado gratuitamente sem uma conta paga da Apple, na primeira vez que alguém abrir a aplicação no Mac deve clicar no ícone com o **botão direito → Abrir**.
'''


def t_notas() -> str:
    """Template de `docs/notas.md` (diário de decisões do projeto)."""
    return '''\
# Notas e Ideias do Projeto

Usa este ficheiro como rascunho pessoal para apontares ideias, coisas a fazer ou notas enquanto programas.

## Ideias

- 

## Tarefas

- [ ] Ler os guias em `docs/` para conhecer a estrutura do projeto
- [ ] Substituir os botões de exemplo do `src/__PKG__/main.py`
- [ ] Personalizar o ícone em `data/icons/scalable/apps/__APPID__.svg`
'''


# ------------------------------------------------------------------
# TEMPLATES — data/ (lançador .desktop, AppStream XML, ícones).
# ------------------------------------------------------------------


def t_desktop() -> str:
    """Template do ficheiro `.desktop` (lançador FreeDesktop)."""
    return '''\
# Lançador do ambiente de trabalho (ficheiro .desktop, formato INI).
#
# Instalação por utilizador (sem root):
#   desktop-file-install --dir=~/.local/share/applications data/__APPID__.desktop
# No .deb, scripts/build_packages.sh instala-o em /usr/share/applications/.
# O Exec aponta para o entry point do pyproject.toml (instalado em /usr/bin).
# Validar sempre:  desktop-file-validate data/__APPID__.desktop

[Desktop Entry]
Type=Application
Version=1.0
Name=__VISIVEL__
GenericName=Aplicação desktop
Comment=__DESC__
Exec=__DIST__
Icon=__APPID__
Terminal=false
Categories=GTK;Utility;
StartupNotify=true
'''


def t_metainfo() -> str:
    """Template do ficheiro `.metainfo.xml` (AppStream).

    [MELHORIA] Usa `__AUTOR_XML__`, `__VISIVEL_XML__` e `__DESC_XML__` para
    garantir XML válido mesmo quando o autor ou descrição têm caracteres especiais.
    """
    return '''\
<?xml version="1.0" encoding="UTF-8"?>
<!-- Metadados AppStream do __VISIVEL_XML__: alimentam os "Software Centers"
     (GNOME Software, Discover); validar com appstreamcli validate.
     O <id> tem de coincidir com o nome do lançador (__APPID__.desktop). -->
<component type="desktop-application">
  <id>__APPID__</id>
  <metadata_license>FSFAP</metadata_license>
  <project_license>GPL-3.0-or-later</project_license>
  <developer_name>__AUTOR_XML__</developer_name>
  <name>__VISIVEL_XML__</name>
  <summary>__DESC_XML__</summary>
  <description>
    <p>__DESC_XML__ Este é o esqueleto inicial gerado por urze —
    substitui esta descrição pela do teu projeto.</p>
  </description>
  <launchable type="desktop-id">__APPID__.desktop</launchable>
  <url type="homepage">__GITHUB__/__DIST__</url>
  <provides>
    <binary>__DIST__</binary>
  </provides>
  <releases>
    <release version="0.1.0" date="__DATA__"/>
  </releases>
  <content_rating type="oars-1.1"/>
</component>
'''


def t_icons_readme() -> str:
    """Template do guia de ícones em `data/icons/README.md`."""
    return '''\
# Ícones do __VISIVEL__

Pasta destinada aos ícones da aplicação. O **urze** já gera um ícone vetorial
funcional de exemplo em `scalable/apps/__APPID__.svg`, pelo que o lançador
`.desktop` e o pacote `.deb` têm um ícone válido desde o primeiro momento.

## Layout recomendado (tema hicolor)

    scalable/apps/__APPID__.svg          ← já incluído (um SVG resolve tudo)
    16x16/apps/__APPID__.png, 22x22/…, 24x24/…, 32x32/…,
    48x48/…, 64x64/…, 128x128/apps/__APPID__.png

## Para personalizar

1. Substitui `scalable/apps/__APPID__.svg` pelo ícone definitivo do teu projeto;
2. Se adicionares variantes PNG por resolução, acrescenta as linhas
   correspondentes a `debian/__DIST__.install` (em `scripts/build_packages.sh`);
3. No `.deb`, o `dh_icons` atualiza as caches de ícones automaticamente.
'''


def t_icon_svg() -> str:
    """Template do ícone vetorial de exemplo em `data/icons/scalable/apps/__APPID__.svg`.

    [MELHORIA] Garante que `Icon=__APPID__` no ficheiro `.desktop` aponta para
    um ficheiro real logo após a criação do projeto e no pacote `.deb`.
    """
    return '''\
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#3584e4"/>
      <stop offset="100%" stop-color="#1a5fb4"/>
    </linearGradient>
  </defs>
  <rect x="12" y="12" width="104" height="104" rx="24" fill="url(#bg)"/>
  <rect x="28" y="32" width="72" height="64" rx="8" fill="#ffffff" fill-opacity="0.92"/>
  <rect x="28" y="32" width="72" height="14" rx="6" fill="#1c71d8"/>
  <circle cx="38" cy="39" r="3" fill="#ffffff"/>
  <circle cx="48" cy="39" r="3" fill="#ffffff" fill-opacity="0.7"/>
  <rect x="40" y="58" width="48" height="8" rx="4" fill="#3584e4"/>
  <rect x="48" y="74" width="32" height="8" rx="4" fill="#99c1f1"/>
</svg>
'''


# ------------------------------------------------------------------
# TEMPLATES — pacote Python (src/__PKG__/…).
# ------------------------------------------------------------------


def t_init() -> str:
    """Template de `src/__PKG__/__init__.py`."""
    return '''\
# Ficha do pacote: docstring e __version__.
# A versão vive APENAS aqui — o hatchling extrai-a daqui para o
# pyproject.toml ([tool.hatch.version]); não a repitas noutro sítio.

"""__VISIVEL__ — __DESC__."""

__version__ = "0.1.0"
'''


def t_main_modulo() -> str:
    """Template de `src/__PKG__/__main__.py` (permite `python -m <pkg>`)."""
    return '''\
# Ponto de entrada de `python -m __PKG__` — é assim que o ./run arranca.
# Apenas delega no main() de main.py; sem lógica própria.

from __PKG__.main import main

if __name__ == "__main__":
    main()
'''


def t_main() -> str:
    """Template de `src/__PKG__/main.py` (janela GTK3 principal).

    [MELHORIA]
    1. Usa `__VISIVEL_XML__` dentro de `rotulo.set_markup(...)` para que
       nomes com '&' ou '<' não quebrem o parser Pango Markup.
    2. Usa o token `__CLASSE__` (que antes estava calculado mas nunca era
       usado) para dar nome à classe da aplicação (`__CLASSE__App`).
    """
    return '''\
# Janela de exemplo com tematização completa, no padrão GTK3 clássico:
# um combo escolhe o esquema (sistema/preto/branco), um FontButton escolhe
# a fonte; as duas mudanças aplicam-se em tempo real via módulo appearance
# e ficam persistidas em ~/.config/__PKG__/aparencia.json.
# Substitui esta janela pela tua — o padrão de tematização mantém-se igual.

import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from .defaults.config import ESQUEMAS, carregar_config, guardar_config
from .modules.appearance import aplicar_tema

ROTULO_ESQUEMA = {"sistema": "Sistema", "preto": "Preto", "branco": "Branco"}


class Janela(Gtk.ApplicationWindow):
    """Janela principal do exemplo, com controlos de aparência em cima."""

    def __init__(self, app: Gtk.Application, config):
        super().__init__(application=app)
        self.config = config
        self.set_title("__VISIVEL__")
        self.set_default_size(760, 500)
        self.set_border_width(12)

        cabecalho = Gtk.HeaderBar()
        cabecalho.set_show_close_button(True)
        cabecalho.set_title("__VISIVEL__")
        cabecalho.set_subtitle("__DESC__")
        self.set_titlebar(cabecalho)

        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.add(caixa)

        # --- controlos de aparência ----------------------------------
        linha = Gtk.Box(spacing=8)
        linha.pack_start(Gtk.Label(label="Esquema de cores:"), False, False, 0)
        self.combo = Gtk.ComboBoxText()
        for esquema in ESQUEMAS:
            self.combo.append_text(ROTULO_ESQUEMA[esquema])
        self.combo.set_active(ESQUEMAS.index(config.esquema_cores))
        self.combo.connect("changed", self._ao_mudar_esquema)
        linha.pack_start(self.combo, False, False, 0)

        linha.pack_start(Gtk.Label(label="Fonte:"), False, False, 0)
        self.botao_fonte = Gtk.FontButton()
        self.botao_fonte.set_font(config.fonte or "Noto Sans 11")
        self.botao_fonte.connect("font-set", self._ao_mudar_fonte)
        linha.pack_start(self.botao_fonte, True, True, 0)
        caixa.pack_start(linha, False, False, 0)

        # --- área de demonstração ------------------------------------
        demo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        demo.set_halign(Gtk.Align.CENTER)
        demo.set_valign(Gtk.Align.CENTER)

        rotulo = Gtk.Label()
        rotulo.set_markup(
            "<span size='x-large' weight='bold'>__VISIVEL_XML__</span>\\n"
            "O tema e a fonte aplicam-se a toda a aplicação, em tempo real."
        )
        rotulo.set_justify(Gtk.Justification.CENTER)
        demo.pack_start(rotulo, False, False, 0)

        amostra = Gtk.Box(spacing=10)
        amostra.set_halign(Gtk.Align.CENTER)
        botao = Gtk.Button(label="Botão de exemplo")
        botao.connect("clicked", lambda *_: print("Botão premido."))
        amostra.pack_start(botao, False, False, 0)
        campo = Gtk.Entry()
        campo.set_placeholder_text("Campo de exemplo")
        amostra.pack_start(campo, False, False, 0)
        interruptor = Gtk.Switch()
        interruptor.set_active(True)
        amostra.pack_start(interruptor, False, False, 0)
        demo.pack_start(amostra, False, False, 0)
        caixa.pack_start(demo, True, True, 0)

        # --- rodapé com o estado -------------------------------------
        self.estado = Gtk.Label(xalign=0)
        caixa.pack_start(self.estado, False, False, 0)

        self.connect("destroy", lambda *_: app.quit())
        self._aplicar()

    def _ao_mudar_esquema(self, combo):
        self.config.esquema_cores = ESQUEMAS[combo.get_active()]
        self._aplicar()

    def _ao_mudar_fonte(self, botao):
        self.config.fonte = botao.get_font()
        self._aplicar()

    def _aplicar(self):
        """Aplica o tema atual e guarda a escolha do utilizador."""
        aplicar_tema(self, self.config)
        guardar_config(self.config)
        fonte = self.config.fonte or "(por omissão do tema)"
        self.estado.set_text(
            f"Esquema: {ROTULO_ESQUEMA[self.config.esquema_cores]}   ·   "
            f"Fonte: {fonte}   ·   guardado em ~/.config/__PKG__/aparencia.json"
        )


class __CLASSE__App(Gtk.Application):
    """Aplicação GTK3 — id __APPID__ (ver data/__APPID__.desktop)."""

    def __init__(self):
        super().__init__(application_id="__APPID__")

    def do_activate(self):
        Janela(self, carregar_config()).show_all()


def main():
    """Ponto de entrada — chamado por __main__.py e pelo entry point __DIST__."""
    GLib.set_application_name("__VISIVEL__")
    __CLASSE__App().run(sys.argv)
'''


def t_core() -> str:
    """Template de `src/__PKG__/core/__init__.py` (contrato `ModuloBase`)."""
    return '''\
# Núcleo: contratos partilhados por todos os módulos. Aqui vivem as
# classes-base, para que os módulos sigam o mesmo ciclo de vida e os
# testes possam confiar numa interface comum.

class ModuloBase:
    """Contrato base de todos os módulos do projeto.

    Cada módulo vive em modules/<nome>/ e expõe a sua API no __init__.py.
    Quando um módulo precisa de ciclo de vida (arrancar/parar, ligar e
    libertar recursos), herda daqui e implementa `ativar`; `desativar`
    tem comportamento neutro por omissão.
    """

    nome: str = ""
    descricao: str = ""

    def ativar(self) -> None:
        """Coloca o módulo em serviço — obrigatório implementar."""
        raise NotImplementedError(f"{type(self).__name__} tem de implementar ativar()")

    def desativar(self) -> None:
        """Liberta o que `ativar` ligou — omissão: nada a fazer."""
        return None

    def __repr__(self) -> str:
        return f"<{type(self).__name__} nome={self.nome!r}>"
'''


def t_views() -> str:
    """Template de `src/__PKG__/views/__init__.py`."""
    return '''\
# Vistas: janelas, diálogos e widgets compostos da interface.
# Convenção: um ficheiro por componente; a lógica de negócio vive em
# modules/, a apresentação aqui. O main.py é a janela principal; quando
# a interface crescer, migra-a para cá (ex.: views/janela_principal.py).
'''


def t_config() -> str:
    """Template de `src/__PKG__/defaults/config.py` (persistência XDG JSON)."""
    return '''\
# Configuração de aparência do utilizador: valores por omissão, validação
# e persistência em ~/.config/__PKG__/aparencia.json (respeita o
# XDG_CONFIG_HOME). Os esquemas disponíveis são fixos — "sistema", "preto",
# "branco" — e os CSS correspondentes vivem neste mesmo diretório.

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ESQUEMAS = ("sistema", "preto", "branco")


@dataclass
class ConfigAparencia:
    """Estado da aparência: esquema de cores e fonte do utilizador."""

    esquema_cores: str = "sistema"   # "sistema" | "preto" | "branco"
    fonte: str = ""                  # "" = fonte do tema; ex.: "Noto Sans 11"


def ficheiro_config() -> Path:
    """Caminho do JSON de configuração (XDG em Linux, APPDATA em Windows, Library em macOS)."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        base = Path(xdg)
    elif os.name == "nt":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".config"
    return base / "__PKG__" / "aparencia.json"


def carregar_config() -> ConfigAparencia:
    """Lê a configuração guardada; regressa às omissões se for inválida."""
    config = ConfigAparencia()
    try:
        dados = json.loads(ficheiro_config().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return config
    if isinstance(dados, dict):
        if dados.get("esquema_cores") in ESQUEMAS:
            config.esquema_cores = dados["esquema_cores"]
        if isinstance(dados.get("fonte"), str):
            config.fonte = dados["fonte"]
    return config


def guardar_config(config: ConfigAparencia) -> None:
    """Persiste a configuração (cria o diretório se for preciso)."""
    caminho = ficheiro_config()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(asdict(config), indent=2, ensure_ascii=False) + "\\n",
        encoding="utf-8",
    )
'''


def t_css_escuro() -> str:
    """Template de `src/__PKG__/defaults/tema_escuro.css`."""
    return '''\
/* Paleta escura — aplicada no esquema "preto" (junto com
   gtk-application-prefer-dark-theme, para afinar com os widgets nativos).
   Editar à vontade: é um CSS GTK3 normal (seletores de widget). */

window { background-color: #1e2027; color: #e8e9ec; }

headerbar {
    background-color: #262a33;
    color: #e8e9ec;
    border-bottom: 1px solid #3a3f4b;
}

label { color: #e8e9ec; }

button {
    background-color: #343946;
    color: #e8e9ec;
    border-radius: 6px;
    padding: 6px 14px;
}
button:hover  { background-color: #3f4554; }
button:active { background-color: #4a5163; }

entry {
    background-color: #262a33;
    color: #e8e9ec;
    border: 1px solid #3a3f4b;
    border-radius: 6px;
    padding: 6px 10px;
}
entry:focus { border-color: #7aa2f7; }

switch { background-color: #343946; }
switch:checked { background-color: #4d6b9e; }

combobox button.combo {
    background-color: #343946;
    color: #e8e9ec;
    border-radius: 6px;
}
'''


def t_css_claro() -> str:
    """Template de `src/__PKG__/defaults/tema_claro.css`."""
    return '''\
/* Paleta clara — aplicada no esquema "branco". Editar à vontade:
   é um CSS GTK3 normal (seletores de widget). */

window { background-color: #f6f6f4; color: #24292f; }

headerbar {
    background-color: #e9e7e2;
    color: #24292f;
    border-bottom: 1px solid #d0cdc7;
}

label { color: #24292f; }

button {
    background-color: #ffffff;
    color: #24292f;
    border: 1px solid #d0cdc7;
    border-radius: 6px;
    padding: 6px 14px;
}
button:hover  { background-color: #f0efec; }
button:active { background-color: #e4e2dd; }

entry {
    background-color: #ffffff;
    color: #24292f;
    border: 1px solid #d0cdc7;
    border-radius: 6px;
    padding: 6px 10px;
}
entry:focus { border-color: #2f6fdb; }

switch { background-color: #d0cdc7; }
switch:checked { background-color: #2f6fdb; }

combobox button.combo {
    background-color: #ffffff;
    color: #24292f;
    border: 1px solid #d0cdc7;
    border-radius: 6px;
}
'''


# ------------------------------------------------------------------
# TEMPLATES — módulo appearance (tematização, copiável entre projetos).
# ------------------------------------------------------------------


def t_appearance_init() -> str:
    """Template de `src/__PKG__/modules/appearance/__init__.py`."""
    return '''\
# API pública do módulo appearance — tematização da aplicação.
#
# Ponto de uso (única função de que o resto do código precisa):
#     from __PKG__.modules.appearance import aplicar_tema
#     aplicar_tema(janela, config)
#
# O que faz: substitui o CSS anterior do ecrã por (CSS do esquema escolhido
# + bloco de fonte) e ajusta gtk-application-prefer-dark-theme. O padrão —
# provider por ecrã, remover o anterior antes de reaplicar — é o GTK3
# clássico (Gtk.CssProvider + StyleContext.add_provider_for_screen).
#
# Copiável entre projetos: depende apenas de GTK3 e de defaults/.

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ...defaults.config import ConfigAparencia
from .fonte import Fonte
from .tema import Tema

__all__ = ["Tema", "Fonte", "aplicar_tema"]


def aplicar_tema(janela: Gtk.Window, config: ConfigAparencia) -> None:
    """Aplica ao ecrã de `janela` o esquema de cores e a fonte de `config`."""
    Tema.aplicar(config.esquema_cores, Fonte.css_da_fonte(config.fonte))
'''


def t_tema() -> str:
    """Template de `src/__PKG__/modules/appearance/tema.py`.

    [MELHORIA] Quando o utilizador escolhe o esquema `"sistema"`, usamos
    `settings.reset_property("gtk-application-prefer-dark-theme")` em vez de
    forçar `False`. Assim, se o ambiente de trabalho estiver em modo escuro,
    o modo `"sistema"` respeita-o verdadeiramente.
    """
    return '''\
# Esquemas de cores via CssProvider (GTK3 clássico).
#
# Funcionamento: um único provider é registado no ecrã; a cada mudança,
# o provider anterior é removido antes de o novo ser aplicado (evita
# acumulação de providers e conflitos de prioridade). O modo "sistema"
# não aplica CSS de cores e repõe a preferência nativa do ambiente;
# "preto" aplica o tema escuro e liga gtk-application-prefer-dark-theme;
# "branco" aplica o tema claro e desliga-a.

import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk

def _localizar_defaults() -> Path:
    """Localiza a pasta `defaults/` (código normal ou congelado com PyInstaller)."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidato = Path(meipass) / "__PKG__" / "defaults"
        if candidato.exists():
            return candidato
    return Path(__file__).resolve().parents[2] / "defaults"


DIRETORIO_PADRAO = _localizar_defaults()
PRIORIDADE = Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION


class Tema:
    """Esquemas de cores: sistema | preto | branco, via CSS por ecrã."""

    _provider = None   # provider atualmente registado (para poder ser removido)

    @staticmethod
    def css_do_esquema(esquema: str) -> str:
        """Devolve o CSS do esquema escolhido; string vazia no modo sistema."""
        nomes = {"preto": "tema_escuro.css", "branco": "tema_claro.css"}
        nome = nomes.get(esquema)
        if nome is None:
            return ""
        caminho = DIRETORIO_PADRAO / nome
        try:
            return caminho.read_text(encoding="utf-8")
        except OSError:
            print(f"appearance: não consegui ler {caminho}", file=sys.stderr)
            return ""

    @staticmethod
    def remover() -> None:
        """Remove o provider atual (antes de reaplicar)."""
        screen = Gdk.Screen.get_default()
        if Tema._provider is not None and screen is not None:
            Gtk.StyleContext.remove_provider_for_screen(screen, Tema._provider)
            Tema._provider = None

    @staticmethod
    def aplicar(esquema: str, css_extra: str = "") -> None:
        """Aplica o esquema + CSS extra (fonte) a todo o ecrã."""
        screen = Gdk.Screen.get_default()
        if screen is None:
            return
        Tema.remover()
        css = Tema.css_do_esquema(esquema) + css_extra
        if css:
            provider = Gtk.CssProvider()
            dados = css.encode("utf-8")
            try:
                provider.load_from_data(dados, len(dados))
            except Exception as erro:   # GLib.Error — CSS inválido
                print(f"appearance: CSS inválido ignorado ({erro})", file=sys.stderr)
                return
            Gtk.StyleContext.add_provider_for_screen(screen, provider, PRIORIDADE)
            Tema._provider = provider

        settings = Gtk.Settings.get_default()
        if settings is not None:
            if esquema == "sistema":
                # Repõe o valor original do ambiente gráfico (claro ou escuro)
                settings.reset_property("gtk-application-prefer-dark-theme")
            else:
                settings.set_property(
                    "gtk-application-prefer-dark-theme", esquema == "preto"
                )
'''


def t_fonte() -> str:
    """Template de `src/__PKG__/modules/appearance/fonte.py`."""
    return '''\
# Fonte do utilizador → CSS. O GTK não aplica uma Pango.FontDescription
# diretamente ao tema; o caminho fiável é converter a descrição escolhida
# no FontButton num bloco CSS global (`* { font-family … }`) injetado no
# mesmo provider do tema. Fonte vazia = respeitar a fonte do tema.

import gi

gi.require_version("Pango", "1.0")
from gi.repository import Pango


class Fonte:
    """Converte uma descrição Pango (ex.: "Noto Sans 11") em CSS global."""

    @staticmethod
    def css_da_fonte(descricao: str) -> str:
        """Devolve um bloco `* { … }`; string vazia se não houver nada a aplicar."""
        descricao = (descricao or "").strip()
        if not descricao:
            return ""
        fonte = Pango.FontDescription.from_string(descricao)
        propriedades = []

        familia = fonte.get_family()
        if familia:
            # Escapa eventuais aspas no nome da família antes de gerar o CSS
            familia_segura = familia.replace('"', "'")
            propriedades.append(f'font-family: "{familia_segura}";')

        tamanho = fonte.get_size() / Pango.SCALE
        if tamanho > 0:
            valor = f"{tamanho:.0f}" if float(tamanho).is_integer() else f"{tamanho:.1f}"
            propriedades.append(f"font-size: {valor}pt;")

        if int(fonte.get_weight()) >= int(Pango.Weight.BOLD):
            propriedades.append("font-weight: bold;")

        if fonte.get_style() == Pango.Style.ITALIC:
            propriedades.append("font-style: italic;")

        if fonte.get_variant() == Pango.Variant.SMALL_CAPS:
            propriedades.append("font-variant: small-caps;")

        if not propriedades:
            return ""
        return "* { " + " ".join(propriedades) + " }\\n"
'''


def t_test_smoke() -> str:
    """Template de `tests/test_smoke.py`.

    [MELHORIA] Adicionados testes de persistência (`guardar_config` +
    `carregar_config` e recuperação perante JSON corrompido) usando as
    fixtures `monkeypatch` e `tmp_path` do `pytest`.
    """
    return '''\
# Testes de fumo: correm SEM GTK (não importam gi), para servirem de base
# a CI mínimo. Testes de interface, se existirem, vivem em ficheiros
# próprios e correm só onde haja servidor gráfico.

import pytest

import __PKG__
from __PKG__.core import ModuloBase
from __PKG__.defaults.config import (
    ESQUEMAS,
    ConfigAparencia,
    carregar_config,
    ficheiro_config,
    guardar_config,
)


def test_versao_definida():
    assert isinstance(__PKG__.__version__, str) and __PKG__.__version__


def test_modulo_base_exige_ativar():
    with pytest.raises(NotImplementedError):
        ModuloBase().ativar()


def test_modulo_base_desativar_neutro():
    ModuloBase().desativar()   # não deve lançar


def test_config_por_omissao():
    config = ConfigAparencia()
    assert config.esquema_cores == "sistema"
    assert config.fonte == ""


def test_esquemas_conhecidos():
    assert set(ESQUEMAS) == {"sistema", "preto", "branco"}


def test_guardar_e_carregar_config(monkeypatch, tmp_path):
    """Garante que a configuração é persistida e lida respeitando XDG_CONFIG_HOME."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    original = ConfigAparencia(esquema_cores="preto", fonte="Sans 12")
    guardar_config(original)

    lida = carregar_config()
    assert lida.esquema_cores == "preto"
    assert lida.fonte == "Sans 12"


def test_carregar_config_json_invalido_usa_omissao(monkeypatch, tmp_path):
    """Se o ficheiro JSON estiver corrompido, regressa às omissões sem crashar."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    caminho = ficheiro_config()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("{json invalido", encoding="utf-8")

    lida = carregar_config()
    assert lida == ConfigAparencia()
'''


# ------------------------------------------------------------------
# TEMPLATES — scripts/ (instalador em 4 fases e empacotamento Debian).
# ------------------------------------------------------------------


def t_install() -> str:
    """Template de `scripts/install.py`.

    [MELHORIAS CRÍTICAS]
    1. `ler_requisitos_apt()` e `versao_suficiente()`: separa corretamente o
       operador Debian (`>=`, `>>`, `=`, `<=`, `<<`) do número da versão antes
       de invocar `dpkg --compare-versions`. Antes passava `">= 1.0"` como
       argumento de versão, o que fazia o `dpkg` falhar sempre.
    2. `fase_pip()`: usa `pip install --no-build-isolation -e .` para construir
       o pacote com o `python3-hatchling` já instalado via `apt`, evitando
       downloads da internet durante a instalação local.
    """
    return '''\
#!/usr/bin/env python3
# Instalador do projeto — prepara tudo num sistema Debian, em 4 fases:
#   1. apt  — valida requirements-apt.txt e instala o que falta
#             (uma única chamada apt-get agregada; sudo só nesta fase;
#             saltada dentro de Flatpak — detetado por FLATPAK_ID);
#   2. venv — cria .venv com --system-site-packages, sem o qual o
#             `import gi` não funciona dentro do venv;
#   3. pip  — instala o próprio projeto: .venv/bin/pip install --no-build-isolation -e .
#   4. verificação — pip check + GTK3 acessível via gi.
#
# Modo de verificação (read-only, para CI):
#   ./scripts/install.py --check   → sai com código 1 se algo faltar.
#
# Idempotente: pode ser corrido quantas vezes for preciso.

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VENV = RAIZ / ".venv"
REQ_APT = RAIZ / "requirements-apt.txt"
DIST = "__DIST__"

# Mapeamento de operadores de debian/control para operadores do `dpkg --compare-versions`
OPERADORES_DPKG = {
    ">=": "ge",
    ">>": "gt",
    ">": "gt",
    "<=": "le",
    "<<": "lt",
    "<": "lt",
    "=": "eq",
    "==": "eq",
}


def ok(msg):
    print(f"  [ok]    {msg}")


def aviso(msg):
    print(f"  [aviso] {msg}")


def erro(msg):
    print(f"  [ERRO]  {msg}", file=sys.stderr)


# --- fase 1: pacotes de sistema --------------------------------------
def ler_requisitos_apt():
    """requirements-apt.txt → [(nome, (operador_dpkg, versão_mínima) | None)]."""
    requisitos = []
    for linha in REQ_APT.read_text(encoding="utf-8").splitlines():
        linha = linha.split("#", 1)[0].strip()
        if not linha:
            continue
        nome, _, resto = linha.partition("(")
        restricao_bruta = resto.strip().rstrip(")").strip()
        restricao = None
        if restricao_bruta:
            # Extrai operador opcional (ex.: '>= 1.2' → op='>=', ver='1.2')
            m = re.match(r"^([<=>]+)?\\s*(.+)$", restricao_bruta)
            if m:
                op_simbolo = m.group(1) or ">="
                op_dpkg = OPERADORES_DPKG.get(op_simbolo, "ge")
                restricao = (op_dpkg, m.group(2).strip())
        requisitos.append((nome.strip(), restricao))
    return requisitos


def estado_pacote(nome):
    """(instalado, versão) via dpkg-query; (None, "") se o dpkg não existir."""
    try:
        resultado = subprocess.run(
            ["dpkg-query", "-W", "-f=${db:Status-Abbrev}|${Version}", nome],
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        return None, ""
    if resultado.returncode:
        return False, ""
    abreviatura, _, versao = resultado.stdout.partition("|")
    return abreviatura.strip() == "ii", versao.strip()


def versao_suficiente(instalada, restricao):
    """Compara versões com o dpkg (mesma semântica do debian/control)."""
    if not restricao:
        return True
    op_dpkg, versao_alvo = restricao
    try:
        return subprocess.run(
            ["dpkg", "--compare-versions", instalada, op_dpkg, versao_alvo],
            capture_output=True,
        ).returncode == 0
    except FileNotFoundError:
        return True   # sem dpkg, não há como comparar — não bloquear


def fase_apt(verificar):
    """Fase 1 — valida e (fora do --check) instala os pacotes apt."""
    if os.environ.get("FLATPAK_ID"):
        aviso("a correr em Flatpak — fase apt saltada (as libs vêm do runtime).")
        return True
    if not REQ_APT.exists():
        aviso("requirements-apt.txt não encontrado — nada a verificar.")
        return True

    faltantes = []
    for nome, restricao in ler_requisitos_apt():
        instalado, versao = estado_pacote(nome)
        if instalado is None:
            erro("dpkg-query indisponível — isto não parece ser um sistema Debian.")
            return False
        if not instalado:
            faltantes.append(nome)
            aviso(f"ausente: {nome}")
        elif not versao_suficiente(versao, restricao):
            _, ver_min = restricao
            faltantes.append(nome)
            aviso(f"desatualizado: {nome} {versao} (requer {ver_min})")
        else:
            ok(f"presente: {nome} {versao}")

    if not faltantes:
        ok("todos os pacotes de sistema estão presentes.")
        return True
    if verificar:
        erro(f"faltam {len(faltantes)} pacote(s): {' '.join(faltantes)}")
        return False

    comando = ["sudo"] if os.geteuid() != 0 else []
    if "sudo" in comando and shutil.which("sudo") is None:
        erro("não és root e o sudo não existe — corre como root.")
        return False
    comando += ["apt-get", "install", "-y", *faltantes]
    print("        $ " + " ".join(comando))
    if subprocess.run(comando).returncode != 0:
        erro("apt-get falhou. Se o índice estiver velho, corre 'sudo apt-get update' e tenta outra vez.")
        return False
    return True


# --- fase 2: venv ------------------------------------------------------
def fase_venv(verificar):
    """Fase 2 — garante .venv com --system-site-packages."""
    python = VENV / "bin" / "python"
    if python.exists():
        cfg = VENV / "pyvenv.cfg"
        texto = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
        if "include-system-site-packages = true" not in texto:
            erro("o .venv existe mas foi criado SEM --system-site-packages;")
            erro("o `import gi` falharia. Recria:  rm -rf .venv && ./scripts/install.py")
            return False
        ok("venv presente (.venv) com acesso às bibliotecas do sistema.")
        return True
    if verificar:
        erro("venv ausente (.venv) — corre ./scripts/install.py.")
        return False
    return subprocess.run(
        [sys.executable, "-m", "venv", ".venv", "--system-site-packages"],
        cwd=RAIZ,
    ).returncode == 0


# --- fase 3: pip -------------------------------------------------------
def fase_pip(verificar):
    """Fase 3 — instala o projeto em modo editável no venv."""
    python = VENV / "bin" / "python"
    if not python.exists():
        erro("venv ausente — a fase 2 falhou?")
        return False
    if verificar:
        instalado = subprocess.run(
            [str(python), "-m", "pip", "show", DIST], capture_output=True
        ).returncode == 0
        if instalado:
            ok(f"pacote {DIST} instalado no venv.")
            return True
        erro(f"pacote {DIST} não instalado no venv.")
        return False
    # Usamos --no-build-isolation para reutilizar o python3-hatchling instalado
    # via apt na fase 1, permitindo instalar mesmo sem ligação à internet.
    return subprocess.run(
        [str(python), "-m", "pip", "install", "--no-build-isolation", "-e", "."],
        cwd=RAIZ,
    ).returncode == 0


# --- fase 4: verificação -----------------------------------------------
def fase_verificar(verificar):
    """Fase 4 — pacote importável + pip check do projeto + GTK3 acessível via gi."""
    python = VENV / "bin" / "python"
    if not python.exists():
        erro("venv ausente — nada a verificar.")
        return False

    em_ordem = True

    # 1. Verifica que o próprio pacote do projeto e o ponto de entrada são importáveis no venv
    resultado_pkg = subprocess.run(
        [str(python), "-c", "import __PKG__, __PKG__.main; print(__PKG__.__version__)"],
        capture_output=True, text=True,
    )
    if resultado_pkg.returncode == 0:
        ok(f"pacote __PKG__ ({resultado_pkg.stdout.strip()}) importável no venv.")
    else:
        erro(f"não foi possível importar __PKG__: {resultado_pkg.stderr.strip()}")
        em_ordem = False

    # 2. Verifica consistência de dependências do projeto no pip check
    # Nota: como o venv usa --system-site-packages, o `pip check` global pode
    # listar avisos de pacotes Debian do sistema alheios ao projeto (ex.: apt-listchanges).
    # Por isso filtramos apenas linhas que digam respeito a este projeto (DIST).
    resultado = subprocess.run(
        [str(python), "-m", "pip", "check"], capture_output=True, text=True
    )
    conflitos_projeto = [
        linha for linha in (resultado.stdout + resultado.stderr).splitlines()
        if linha.lower().startswith(DIST.lower() + " ")
    ]
    if not conflitos_projeto:
        ok("pip check: dependências do projeto consistentes.")
    else:
        erro("pip check: " + "; ".join(conflitos_projeto))
        em_ordem = False

    # 3. Verifica que o GTK3 está acessível no venv
    resultado = subprocess.run(
        [str(python), "-c",
         "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk"],
        capture_output=True, text=True,
    )
    if resultado.returncode == 0:
        ok("GTK3 acessível no venv (gi).")
    else:
        ultima = (resultado.stderr.strip().splitlines() or ["?"])[-1]
        erro(f"GTK3 não acessível no venv: {ultima}")
        em_ordem = False
    return em_ordem


FASES = [
    ("pacotes de sistema (apt)", fase_apt),
    ("ambiente virtual (venv)", fase_venv),
    ("projeto no venv (pip -e .)", fase_pip),
    ("verificação final", fase_verificar),
]


def main():
    parser = argparse.ArgumentParser(
        description="Instala/verifica o ambiente do projeto, em 4 fases."
    )
    parser.add_argument(
        "--check", action="store_true",
        help="só verifica, sem instalar (para CI); sai com 1 se faltar algo",
    )
    args = parser.parse_args()

    for numero, (nome, fase) in enumerate(FASES, 1):
        print(f"[{numero}/4] {nome}")
        if not fase(args.check):
            erro(f"interrompido na fase {numero} — {nome}.")
            return 1
    if args.check:
        ok("verificação concluída: tudo em ordem.")
    else:
        ok("tudo pronto. Corre: ./run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def t_build() -> str:
    """Template de `scripts/build_packages.sh`.

    [MELHORIA] Adicionado `python3-all` à verificação de pacotes de build
    para coincidir exatamente com o `Build-Depends` gerado em `debian/control`.
    """
    return r'''\
#!/usr/bin/env bash
# Empacotamento Debian: gera debian/ a partir de requirements-apt.txt
# (Depends:) e do pyproject.toml, e constrói o .deb com o pybuild.
#
# Requer (verificado em baixo): debhelper, dh-python,
#   pybuild-plugin-pyproject, python3-all, python3-hatchling, build-essential.
# Idempotente: debian/changelog só se escreve à primeira vez (histórico
# é teu); control, rules, install e format são regenerados a cada corrida.
# Fonte do Depends: requirements-apt.txt — edita lá e volta a correr.
#
# Saída: ../__DIST___<versão>_<arquitetura>.deb

set -euo pipefail
cd "$(dirname "$0")/.."

DIST="__DIST__"
PKG="__PKG__"
MANTENEDOR="__AUTOR__ <__AUTOR__@users.noreply.github.com>"

# Versão: fonte única = src/${PKG}/__init__.py
VERSAO=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "src/${PKG}/__init__.py")
if [[ -z "$VERSAO" ]]; then
    echo "Não encontrei __version__ em src/${PKG}/__init__.py" >&2
    exit 1
fi

# Verifica as ferramentas de build (não instala: isso é decisão do utilizador)
faltantes=()
for pacote in debhelper dh-python pybuild-plugin-pyproject python3-all python3-hatchling build-essential; do
    dpkg-query -W -f='${Status}' "$pacote" 2>/dev/null | grep -q "install ok installed" || faltantes+=("$pacote")
done
if [[ ${#faltantes[@]} -gt 0 ]]; then
    echo "Faltam pacotes de build: ${faltantes[*]}"
    echo "Instala com: sudo apt-get install ${faltantes[*]}"
    exit 1
fi

# Depends: a partir da fonte única de dependências de sistema
# (comentários cortados, espaços removidos, versões normalizadas)
DEPENDS=$(sed 's/#.*//' requirements-apt.txt \
            | sed '/^[[:space:]]*$/d' \
            | tr -d ' ' \
            | sed -E 's/\(([<=>!]+)([^)]+)\)/(\1 \2)/g' \
            | sed -E 's/([a-z0-9])\(/\1 (/g' \
            | paste -sd, -)

echo "Depends: python3, ${DEPENDS}"

mkdir -p debian/source

if [[ ! -f debian/changelog ]]; then
    cat > debian/changelog <<FIM
__DIST__ (${VERSAO}-1) unstable; urgency=low

  * Versão inicial gerada por urze.

 -- ${MANTENEDOR}  $(LC_ALL=C date -R)
FIM
fi

cat > debian/control <<FIM
Source: ${DIST}
Section: utils
Priority: optional
Maintainer: ${MANTENEDOR}
Build-Depends: debhelper-compat (= 13), dh-python, pybuild-plugin-pyproject, python3-all, python3-hatchling
Standards-Version: 4.6.2
Homepage: __GITHUB__/__DIST__
Rules-Requires-Root: no

Package: ${DIST}
Architecture: all
Depends: python3, ${DEPENDS}, ${misc:Depends}
Description: __DESC__
 __DESC__ Esqueleto gerado por urze — edita este control ou o
 requirements-apt.txt (fonte do Depends:) e reconstrói.
FIM

# Make exige TAB antes de dh — por isso esta linha vai pelo printf.
cat > debian/rules <<'FIM'
#!/usr/bin/make -f
export PYBUILD_NAME=__DIST__

%:
FIM
printf '\tdh $@ --with python3 --buildsystem=pybuild\n' >> debian/rules
chmod +x debian/rules

# Ficheiros extra do pacote binário (desktop + metainfo + ícone SVG)
cat > "debian/${DIST}.install" <<FIM
data/__APPID__.desktop usr/share/applications/
data/__APPID__.metainfo.xml usr/share/metainfo/
data/icons/scalable/apps/__APPID__.svg usr/share/icons/hicolor/scalable/apps/
FIM

echo "3.0 (native)" > debian/source/format

dpkg-buildpackage -us -uc -b
echo
echo ".deb construído em: $(dirname "$PWD")/"
'''


def t_build_appimage() -> str:
    """Template de `scripts/build_appimage.sh` — gera `.AppImage` portátil para Linux."""
    return r'''\
#!/usr/bin/env bash
# Empacotamento AppImage: monta um AppDir autónomo em build/AppDir/ com o
# código do projeto, lançador .desktop, metadados AppStream e ícone SVG,
# e empacota tudo num ficheiro executável único (.AppImage).
#
# Se o `appimagetool` não estiver instalado no sistema, descarrega a versão
# oficial estática para `build/appimagetool-x86_64.AppImage`.
#
# Saída: ../__DIST__-<versão>-x86_64.AppImage

set -euo pipefail
cd "$(dirname "$0")/.."

DIST="__DIST__"
PKG="__PKG__"
APPID="__APPID__"
ARCH="$(uname -m)"

VERSAO=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "src/${PKG}/__init__.py")
if [[ -z "$VERSAO" ]]; then
    echo "Não encontrei __version__ em src/${PKG}/__init__.py" >&2
    exit 1
fi

APPDIR="$PWD/build/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" \
         "$APPDIR/usr/lib/python3/dist-packages" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/metainfo" \
         "$APPDIR/usr/share/icons/hicolor/scalable/apps"

echo "[1/4] A copiar pacote Python e recursos para AppDir..."
cp -r "src/${PKG}" "$APPDIR/usr/lib/python3/dist-packages/"

# Lançador e ícone exigidos na raiz do AppDir e em usr/share/
cp "data/${APPID}.desktop" "$APPDIR/${APPID}.desktop"
cp "data/${APPID}.desktop" "$APPDIR/usr/share/applications/${APPID}.desktop"
cp "data/${APPID}.metainfo.xml" "$APPDIR/usr/share/metainfo/${APPID}.metainfo.xml"
cp "data/icons/scalable/apps/${APPID}.svg" "$APPDIR/${APPID}.svg"
cp "data/icons/scalable/apps/${APPID}.svg" "$APPDIR/usr/share/icons/hicolor/scalable/apps/${APPID}.svg"
ln -sf "${APPID}.svg" "$APPDIR/.DirIcon"

echo "[2/4] A criar script de arranque AppRun..."
cat > "$APPDIR/AppRun" <<'FIM'
#!/usr/bin/env bash
set -euo pipefail
HERE="$(dirname "$(readlink -f "$0")")"
export PYTHONPATH="${HERE}/usr/lib/python3/dist-packages:${PYTHONPATH:-}"
export XDG_DATA_DIRS="${HERE}/usr/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
exec python3 -m __PKG__ "$@"
FIM
chmod 755 "$APPDIR/AppRun"

cat > "$APPDIR/usr/bin/${DIST}" <<'FIM'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "$0")")/../.."
exec "$HERE/AppRun" "$@"
FIM
chmod 755 "$APPDIR/usr/bin/${DIST}"

echo "[3/4] A localizar appimagetool..."
APPIMAGETOOL=""
if command -v appimagetool >/dev/null 2>&1; then
    APPIMAGETOOL="appimagetool"
else
    LOCAL_TOOL="$PWD/build/appimagetool-${ARCH}.AppImage"
    if [[ ! -x "$LOCAL_TOOL" ]]; then
        echo "  appimagetool não encontrado no sistema; a descarregar para build/..."
        URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage"
        if command -v curl >/dev/null 2>&1; then
            curl -fL "$URL" -o "$LOCAL_TOOL"
        elif command -v wget >/dev/null 2>&1; then
            wget -q "$URL" -O "$LOCAL_TOOL"
        else
            echo "Erro: instala 'appimagetool', 'curl' ou 'wget' para gerar a AppImage." >&2
            exit 1
        fi
        chmod +x "$LOCAL_TOOL"
    fi
    APPIMAGETOOL="$LOCAL_TOOL"
fi

SAIDA="$(dirname "$PWD")/${DIST}-${VERSAO}-${ARCH}.AppImage"
echo "[4/4] A construir ${SAIDA}..."
ARCH="$ARCH" "$APPIMAGETOOL" --appimage-extract-and-run "$APPDIR" "$SAIDA"
chmod +x "$SAIDA"
echo
echo "AppImage construída em: ${SAIDA}"
'''


def t_build_windows() -> str:
    """Template de `scripts/build_windows.sh` — Modo Pasta (--onedir) + Instalador Inno Setup."""
    return r'''\
#!/usr/bin/env bash
# Empacotamento para Windows (Modo Pasta --onedir + Instalador Setup.exe):
# Desenhado para correr dentro do ambiente MSYS2 MINGW64 em Windows
# (localmente num PC/VM Windows ou automaticamente via GitHub Actions).
#
# Porquê --onedir + Instalador:
#   Em aplicações GTK3, o modo --onefile descompacta dezenas de DLLs a cada
#   arranque (demorando 5 a 10 segundos a abrir). O modo --onedir cria uma
#   pasta que abre instantaneamente e é depois empacotada num instalador
#   clássico de Windows (Inno Setup) e num .zip portátil.
#
# Saídas em dist/:
#   - dist/__DIST__/                                 (pasta executável)
#   - dist/__DIST__-<versão>-windows-portable.zip    (ZIP portátil)
#   - dist/Setup-__DIST__-<versão>.exe               (Instalador Windows, se Inno Setup presente)

set -euo pipefail
cd "$(dirname "$0")/.."

DIST="__DIST__"
PKG="__PKG__"
VISIVEL="__VISIVEL__"
APPID="__APPID__"
AUTOR="__AUTOR__"
GITHUB="__GITHUB__"

if [[ "${MSYSTEM:-}" != "MINGW64" && "${OS:-}" != "Windows_NT" ]]; then
    echo "Este script deve ser executado no Windows dentro do terminal 'MSYS2 MINGW64'" >&2
    echo "(ou automaticamente na nuvem através de .github/workflows/build.yml)." >&2
    exit 1
fi

VERSAO=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "src/${PKG}/__init__.py")
if [[ -z "$VERSAO" ]]; then
    echo "Não encontrei __version__ em src/${PKG}/__init__.py" >&2
    exit 1
fi

echo "[1/5] A verificar dependências MSYS2 (Python + GTK3 + PyGObject)..."
if command -v pacman >/dev/null 2>&1; then
    pacman -S --needed --noconfirm \
        mingw-w64-x86_64-python \
        mingw-w64-x86_64-python-pip \
        mingw-w64-x86_64-python-gobject \
        mingw-w64-x86_64-gtk3 \
        mingw-w64-x86_64-librsvg \
        mingw-w64-x86_64-python-pillow \
        zip
fi

echo "[2/5] A preparar PyInstaller e ícone .ico..."
python3 -m pip install --upgrade --no-warn-script-location pyinstaller
python3 -m pip install --no-build-isolation --no-deps .

mkdir -p build dist
ICO_PATH="build/${DIST}.ico"
SVG_PATH="data/icons/scalable/apps/${APPID}.svg"

# Converte o ícone SVG do projeto num ficheiro .ico para o executável Windows
python3 - "$SVG_PATH" "$ICO_PATH" <<'PYEOF'
import sys
import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf
from PIL import Image

svg_in, ico_out = sys.argv[1], sys.argv[2]
pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(svg_in, 256, 256, True)
ok, png_bytes = pixbuf.save_to_bufferv("png", [], [])
if ok:
    import io
    img = Image.open(io.BytesIO(png_bytes))
    img.save(ico_out, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
PYEOF

echo "[3/5] A construir executável em Modo Pasta (--onedir) com PyInstaller..."
pyinstaller \
    --noconfirm \
    --clean \
    --onedir \
    --windowed \
    --name "${DIST}" \
    --icon "${ICO_PATH}" \
    --paths "src" \
    --add-data "src/${PKG}/defaults;${PKG}/defaults" \
    "src/${PKG}/__main__.py"

echo "[4/5] A criar arquivo ZIP portátil..."
(
    cd dist
    rm -f "${DIST}-${VERSAO}-windows-portable.zip"
    zip -rq "${DIST}-${VERSAO}-windows-portable.zip" "${DIST}"
)
echo "  ZIP portátil: dist/${DIST}-${VERSAO}-windows-portable.zip"

echo "[5/5] A gerar script do instalador Inno Setup (build/installer.iss)..."
cat > build/installer.iss <<FIM
[Setup]
AppId={{${APPID}}
AppName=${VISIVEL}
AppVersion=${VERSAO}
AppPublisher=${AUTOR}
AppPublisherURL=${GITHUB}/${DIST}
DefaultDirName={autopf}\\${VISIVEL}
DefaultGroupName=${VISIVEL}
OutputDir=..\\dist
OutputBaseFilename=Setup-${DIST}-${VERSAO}
SetupIconFile=${ICO_PATH}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\\Portuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\\dist\\${DIST}\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\\${VISIVEL}"; Filename: "{app}\\${DIST}.exe"
Name: "{autodesktop}\\${VISIVEL}"; Filename: "{app}\\${DIST}.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\\${DIST}.exe"; Description: "{cm:LaunchProgram,${VISIVEL}}"; Flags: nowait postinstall skipifsilent
FIM

ISCC_BIN=""
if command -v ISCC.exe >/dev/null 2>&1; then
    ISCC_BIN="ISCC.exe"
elif [[ -x "/c/Program Files (x86)/Inno Setup 6/ISCC.exe" ]]; then
    ISCC_BIN="/c/Program Files (x86)/Inno Setup 6/ISCC.exe"
elif [[ -x "/c/Program Files/Inno Setup 6/ISCC.exe" ]]; then
    ISCC_BIN="/c/Program Files/Inno Setup 6/ISCC.exe"
fi

if [[ -n "$ISCC_BIN" ]]; then
    "$ISCC_BIN" "build/installer.iss"
    echo "  Instalador Windows criado em: dist/Setup-${DIST}-${VERSAO}.exe"
else
    echo "  [aviso] Inno Setup (ISCC.exe) não encontrado; instalador .exe saltado."
    echo "          A pasta executável e o .zip portátil estão prontos em dist/."
fi
'''


def t_build_macos() -> str:
    """Template de `scripts/build_macos.sh` — Aplicação `.app` + Instalador `.dmg` para Apple macOS."""
    return r'''\
#!/usr/bin/env bash
# Empacotamento para Apple macOS (.app + Instalador .dmg):
# Desenhado para correr em macOS (localmente num Mac com Homebrew ou
# automaticamente na nuvem através de GitHub Actions `macos-latest`).
#
# Saídas em dist/:
#   - dist/__DIST__.app                      (Aplicação macOS em modo pasta/bundle)
#   - dist/__DIST__-<versão>-macos.dmg       (Imagem de disco instaladora para Mac)

set -euo pipefail
cd "$(dirname "$0")/.."

DIST="__DIST__"
PKG="__PKG__"
VISIVEL="__VISIVEL__"
APPID="__APPID__"

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "Este script deve ser executado num sistema Apple macOS" >&2
    echo "(ou automaticamente na nuvem através de .github/workflows/build.yml)." >&2
    exit 1
fi

VERSAO=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "src/${PKG}/__init__.py")
if [[ -z "$VERSAO" ]]; then
    echo "Não encontrei __version__ em src/${PKG}/__init__.py" >&2
    exit 1
fi

echo "[1/5] A verificar dependências Homebrew (Python + GTK3 + PyGObject)..."
if command -v brew >/dev/null 2>&1; then
    brew install pygobject3 gtk+3 librsvg adwaita-icon-theme
fi

echo "[2/5] A preparar ambiente e PyInstaller..."
python3 -m venv .venv-macos --system-site-packages
.venv-macos/bin/pip install --upgrade pip pyinstaller
.venv-macos/bin/pip install --no-build-isolation --no-deps .

mkdir -p build dist
SVG_PATH="data/icons/scalable/apps/${APPID}.svg"
ICONSET_DIR="build/${DIST}.iconset"
ICNS_PATH="build/${DIST}.icns"

echo "[3/5] A converter ícone SVG para formato Apple (.icns)..."
rm -rf "$ICONSET_DIR"
mkdir -p "$ICONSET_DIR"
for sz in 16 32 128 256 512; do
    rsvg-convert -w "$sz" -h "$sz" "$SVG_PATH" -o "${ICONSET_DIR}/icon_${sz}x${sz}.png"
    sz2=$((sz * 2))
    rsvg-convert -w "$sz2" -h "$sz2" "$SVG_PATH" -o "${ICONSET_DIR}/icon_${sz}x${sz}@2x.png"
done
iconutil -c icns "$ICONSET_DIR" -o "$ICNS_PATH"

echo "[4/5] A construir aplicação ${DIST}.app com PyInstaller..."
.venv-macos/bin/pyinstaller \
    --noconfirm \
    --clean \
    --onedir \
    --windowed \
    --name "${DIST}" \
    --icon "${ICNS_PATH}" \
    --osx-bundle-identifier "${APPID}" \
    --paths "src" \
    --add-data "src/${PKG}/defaults:${PKG}/defaults" \
    "src/${PKG}/__main__.py"

echo "[5/5] A criar instalador de disco (.dmg)..."
DMG_STAGING="build/dmg_staging"
DMG_SAIDA="dist/${DIST}-${VERSAO}-macos.dmg"
rm -rf "$DMG_STAGING" "$DMG_SAIDA"
mkdir -p "$DMG_STAGING"
cp -R "dist/${DIST}.app" "$DMG_STAGING/"
ln -s /Applications "$DMG_STAGING/Applications"

hdiutil create \
    -volname "${VISIVEL}" \
    -srcfolder "$DMG_STAGING" \
    -ov \
    -format UDZO \
    "$DMG_SAIDA"

echo
echo "Instalador macOS criado em: ${DMG_SAIDA}"
'''


def t_github_workflow() -> str:
    """Template de `.github/workflows/build.yml` — gera .deb, AppImage, Windows .exe e macOS .dmg."""
    return r'''\
# Automação GitHub Actions: sempre que envias código (push/PR) para o GitHub,
# este ficheiro corre os testes e constrói automaticamente:
#   1. Pacote Debian (.deb) e AppImage portátil (em Linux);
#   2. Pasta executável (--onedir), ZIP portátil e Instalador Setup.exe (em Windows);
#   3. Aplicação (.app) e Instalador de disco (.dmg) (em Apple macOS).
# Os ficheiros prontos ficam disponíveis para download no separador "Actions" do GitHub.

name: Testes e Instaladores (Linux + Windows + macOS)

on:
  push:
    branches: ["main", "master"]
    tags: ["v*"]
  pull_request:
  workflow_dispatch:

jobs:
  linux:
    name: Linux (.deb + AppImage)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Instalar dependências e criar ambiente
        run: |
          sudo apt-get update
          sudo apt-get install -y debhelper dh-python pybuild-plugin-pyproject python3-all python3-hatchling build-essential file
          ./scripts/install.py

      - name: Correr testes (pytest)
        run: |
          .venv/bin/pip install pytest
          .venv/bin/python -m pytest -q

      - name: Construir pacote Debian (.deb)
        run: ./scripts/build_packages.sh

      - name: Construir AppImage
        run: ./scripts/build_appimage.sh

      - name: Publicar instaladores Linux
        uses: actions/upload-artifact@v4
        with:
          name: instaladores-linux
          path: |
            ../*.deb
            ../*.AppImage

  windows:
    name: Windows (Modo Pasta + Instalador .exe)
    runs-on: windows-latest
    defaults:
      run:
        shell: msys2 {0}
    steps:
      - uses: actions/checkout@v4

      - name: Configurar MSYS2 (MINGW64 + GTK3)
        uses: msys2/setup-msys2@v2
        with:
          msystem: MINGW64
          update: true
          install: >-
            mingw-w64-x86_64-python
            mingw-w64-x86_64-python-pip
            mingw-w64-x86_64-python-pytest
            mingw-w64-x86_64-python-gobject
            mingw-w64-x86_64-gtk3
            mingw-w64-x86_64-librsvg
            mingw-w64-x86_64-python-pillow
            zip

      - name: Correr testes (pytest)
        run: PYTHONPATH=src python3 -m pytest -q

      - name: Construir Executável (--onedir) + Instalador Windows
        run: ./scripts/build_windows.sh

      - name: Publicar instaladores Windows
        uses: actions/upload-artifact@v4
        with:
          name: instaladores-windows
          path: |
            dist/Setup-*.exe
            dist/*-windows-portable.zip

  macos:
    name: Apple macOS (.app + Instalador .dmg)
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4

      - name: Instalar GTK3 e PyGObject via Homebrew
        run: |
          brew install pygobject3 gtk+3 librsvg adwaita-icon-theme pytest

      - name: Correr testes (pytest)
        run: PYTHONPATH=src python3 -m pytest -q

      - name: Construir Aplicação (.app) e Instalador (.dmg)
        run: ./scripts/build_macos.sh

      - name: Publicar instalador macOS
        uses: actions/upload-artifact@v4
        with:
          name: instaladores-macos
          path: dist/*.dmg
'''


# ------------------------------------------------------------------
# ESCRITA — registo de ficheiros, cabeçalhos por tipo e LICENSE.
# ------------------------------------------------------------------

# Tabela declarativa de todos os ficheiros que compõem o esqueleto:
#   (caminho_relativo, descrição_do_papel, função_template, é_executável)
# Quando `função_template` é None (ex.: `py.typed`), cria um ficheiro vazio
# sem cabeçalho, conforme exigido pela PEP 561.
FICHEIROS = [
    ("run", "arranque em desenvolvimento (venv + python -m)", t_run, True),
    ("install.sh", "instalador da aplicação (ambiente + atalho no menu)", t_install_sh, True),
    ("uninstall.sh", "desinstalador da aplicação (remove atalho, comando e .venv)", t_uninstall_sh, True),
    ("pyproject.toml", "fonte única de metadados e dependências Python", t_pyproject, False),
    ("requirements.txt", "lock Python gerado (opcional)", t_requirements, False),
    ("requirements-apt.txt", "dependências de sistema Debian", t_requirements_apt, False),
    (".gitignore", "artefactos locais a não versionar", t_gitignore, False),
    ("README.md", "apresentação do projeto (a preencher)", t_readme, False),
    ("ARCHITECTURE.md", "registo da estrutura do projeto (a preencher)", t_architecture, False),
    ("CHANGELOG.md", "histórico de versões (a preencher)", t_changelog, False),
    ("CONTRIBUTING.md", "guia rápido de contribuição (a preencher)", t_contributing, False),
    ("SECURITY.md", "política de segurança (a preencher)", t_security, False),
    ("docs/1-para-que-serve-cada-pasta-e-ficheiro.md", "explicação simples de todas as pastas e ficheiros", t_doc_pastas_e_ficheiros, False),
    ("docs/2-como-funciona-o-instalador-e-o-arranque.md", "explicação simples do install.py e do ./run", t_doc_instalador_e_arranque, False),
    ("docs/3-onde-escrever-o-teu-codigo.md", "guia prático de onde criar funções e janelas", t_doc_onde_escrever_codigo, False),
    ("docs/4-como-mudar-cores-letra-e-icone.md", "guia para personalizar cores, fonte e ícone", t_doc_cores_letra_e_icone, False),
    ("docs/5-como-adicionar-extras-e-criar-instaladores.md", "guia para pacotes extra e instaladores (.deb, AppImage, Windows)", t_doc_extras_e_deb, False),
    ("docs/notas.md", "bloco de notas e ideias do projeto", t_notas, False),
    ("data/__APPID__.desktop", "lançador do ambiente de trabalho", t_desktop, False),
    ("data/__APPID__.metainfo.xml", "metadados AppStream", t_metainfo, False),
    ("data/icons/README.md", "guia dos ícones", t_icons_readme, False),
    ("data/icons/scalable/apps/__APPID__.svg", "ícone vetorial de exemplo (hicolor)", t_icon_svg, False),
    ("scripts/install.py", "instalador em 4 fases + modo --check", t_install, True),
    ("scripts/build_packages.sh", "empacotamento Debian (.deb)", t_build, True),
    ("scripts/build_appimage.sh", "empacotamento portátil Linux (.AppImage)", t_build_appimage, True),
    ("scripts/build_windows.sh", "empacotamento Windows (--onedir + Instalador .exe)", t_build_windows, True),
    ("scripts/build_macos.sh", "empacotamento Apple macOS (.app + Instalador .dmg)", t_build_macos, True),
    (".github/workflows/build.yml", "automação GitHub Actions (Linux + Windows + macOS)", t_github_workflow, False),
    ("tests/test_smoke.py", "testes de fumo sem GTK", t_test_smoke, False),
    ("src/__PKG__/__init__.py", "ficha do pacote e __version__", t_init, False),
    ("src/__PKG__/__main__.py", "entrada de python -m", t_main_modulo, False),
    ("src/__PKG__/py.typed", None, None, False),
    ("src/__PKG__/main.py", "janela de exemplo GTK3 com tematização", t_main, False),
    ("src/__PKG__/core/__init__.py", "contratos partilhados (ModuloBase)", t_core, False),
    ("src/__PKG__/defaults/config.py", "config de aparência e persistência", t_config, False),
    ("src/__PKG__/defaults/tema_escuro.css", "paleta escura do exemplo", t_css_escuro, False),
    ("src/__PKG__/defaults/tema_claro.css", "paleta clara do exemplo", t_css_claro, False),
    ("src/__PKG__/views/__init__.py", "pasta das vistas da interface", t_views, False),
    ("src/__PKG__/modules/appearance/__init__.py", "API do módulo appearance", t_appearance_init, False),
    ("src/__PKG__/modules/appearance/tema.py", "esquemas de cores via CssProvider", t_tema, False),
    ("src/__PKG__/modules/appearance/fonte.py", "fonte do utilizador convertida em CSS", t_fonte, False),
]


def estilo_para(relativo: str) -> str:
    """Escolhe o estilo de comentário do cabeçalho consoante a extensão."""
    if relativo.endswith(".css"):
        return "css"
    if relativo.endswith((".md", ".xml", ".svg")):
        return "html"
    return "#"


def deve_escrever_ficheiro(ctx: ContextoProjeto, alvo: Path, relativo: str) -> bool:
    """Verifica se `alvo` já existe e, se existir, pergunta se escreve ou ignora.

    Opções aceites na pergunta interativa:
      - `s` / `e` : escrever (sobrescrever) este ficheiro
      - `n` / `i` : ignorar (manter o ficheiro existente — opção por omissão no Enter)
      - `t` / `E` : escrever TODOS os ficheiros existentes seguintes sem voltar a perguntar
      - `I`       : ignorar TODOS os ficheiros existentes seguintes sem voltar a perguntar
    """
    if not alvo.exists():
        return True

    if ctx.politica_existentes == "escrever_todos":
        return True
    if ctx.politica_existentes == "ignorar_todos":
        print(f"  [ignorado] {relativo}")
        return False

    if ctx.nao_interativo or not sys.stdin.isatty():
        print(f"  [ignorado] {relativo} (já existe)")
        return False

    while True:
        try:
            resp = input(
                f"  Ficheiro '{relativo}' já existe. "
                "[e]screver / [i]gnorar / [t]odos escrever / [I]gnorar todos? [i]: "
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            resp = "i"

        if not resp or resp in ("i", "n", "nao", "não", "ignorar"):
            print(f"  [ignorado] {relativo}")
            return False
        if resp in ("e", "s", "sim", "escrever"):
            return True
        if resp in ("t", "E", "todos"):
            ctx.politica_existentes = "escrever_todos"
            return True
        if resp == "I":
            ctx.politica_existentes = "ignorar_todos"
            print(f"  [ignorado] {relativo}")
            return False
        print("    Responde 'e' (escrever), 'i' (ignorar), 't' (escrever todos) ou 'I' (ignorar todos).")


def escrever(
    ctx: ContextoProjeto,
    raiz: Path,
    relativo: str,
    papel: str,
    corpo: str,
    executavel: bool,
) -> None:
    """Escreve um ficheiro do projeto aplicando tokens, cabeçalho e permissões.

    Se o ficheiro já existir, pergunta ao utilizador se quer escrever por cima
    ou ignorar. Se começar por shebang (`#!`) ou declaração XML (`<?xml`),
    mantém essa primeira linha no topo e insere o cabeçalho logo a seguir.
    """
    alvo = raiz / relativo
    if not deve_escrever_ficheiro(ctx, alvo, relativo):
        return
    alvo.parent.mkdir(parents=True, exist_ok=True)
    conteudo = subst(corpo, ctx).lstrip("\n")
    bloco_cabec = cabec(ctx, Path(relativo).name, papel, estilo_para(relativo))

    if conteudo.startswith("#!") or conteudo.startswith("<?xml"):
        primeira, _, resto = conteudo.partition("\n")
        conteudo = primeira + "\n" + bloco_cabec + resto
    else:
        conteudo = bloco_cabec + conteudo

    alvo.write_text(conteudo, encoding="utf-8")
    if executavel:
        alvo.chmod(0o755)


def escrever_licenca(ctx: ContextoProjeto, raiz: Path) -> None:
    """Cria o ficheiro `LICENSE.md` com o texto integral da GPL-3.0 e aviso personalizado.

    Num sistema Debian, lê diretamente `/usr/share/common-licenses/GPL-3`
    (instantâneo e offline). Só tenta descarregar de gnu.org se o ficheiro
    local não existir. Acrescenta no final o bloco de aplicação da licença
    preenchido com o nome, descrição, ano e autor do novo projeto.
    """
    alvo = raiz / "LICENSE.md"
    if not deve_escrever_ficheiro(ctx, alvo, "LICENSE.md"):
        return

    texto = ""
    local = Path("/usr/share/common-licenses/GPL-3")
    if local.exists():
        texto = local.read_text(encoding="utf-8", errors="replace")
    else:
        try:
            import urllib.request

            with urllib.request.urlopen(
                "https://www.gnu.org/licenses/gpl-3.0.txt", timeout=15
            ) as resposta:
                texto = resposta.read().decode("utf-8")
        except OSError:
            texto = ""

    ano = ctx.data[:4]
    apendice_projeto = (
        "\n\n---\n\n"
        f"## Registo de Copyright do Projeto — {ctx.visivel}\n\n"
        "```text\n"
        f"    {ctx.dist} — {ctx.desc}\n"
        f"    Copyright (C) {ano}  {ctx.autor} ({ctx.github})\n\n"
        "    This program is free software: you can redistribute it and/or modify\n"
        "    it under the terms of the GNU General Public License as published by\n"
        "    the Free Software Foundation, either version 3 of the License, or\n"
        "    (at your option) any later version.\n\n"
        "    This program is distributed in the hope that it will be useful,\n"
        "    but WITHOUT ANY WARRANTY; without even the implied warranty of\n"
        "    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the\n"
        "    GNU General Public License for more details.\n\n"
        "    You should have received a copy of the GNU General Public License\n"
        "    along with this program.  If not, see <https://www.gnu.org/licenses/>.\n"
        "```\n"
    )

    if texto:
        alvo.write_text(texto.rstrip() + apendice_projeto, encoding="utf-8")
    else:
        alvo.write_text(
            cabec(ctx, "LICENSE.md", "texto integral da GNU General Public License v3.0", estilo="html")
            + "# GNU General Public License v3.0\n\n"
            "Descarrega o texto oficial para aqui:\n"
            "  https://www.gnu.org/licenses/gpl-3.0.txt\n"
            + apendice_projeto,
            encoding="utf-8",
        )
        print("  [aviso] LICENSE.md: texto da GPL-3.0 indisponível localmente e online.")
        print("          Descarrega-o manualmente de https://www.gnu.org/licenses/gpl-3.0.txt")


def gerar(ctx: ContextoProjeto, raiz: Path) -> None:
    """Percorre a tabela `FICHEIROS` e materializa toda a estrutura em `raiz`."""
    for relativo, papel, gerador, executavel in FICHEIROS:
        relativo_final = subst(relativo, ctx)
        if gerador is None:
            caminho_vazio = raiz / relativo_final
            if not deve_escrever_ficheiro(ctx, caminho_vazio, relativo_final):
                continue
            caminho_vazio.parent.mkdir(parents=True, exist_ok=True)
            caminho_vazio.write_text("", encoding="utf-8")
            continue
        escrever(ctx, raiz, relativo_final, papel, gerador(), executavel)
    escrever_licenca(ctx, raiz)


def mostrar_arvore(raiz: Path) -> None:
    """Imprime no terminal a árvore visual de pastas e ficheiros criados."""
    print(f"\n{raiz.name}/")

    def caminhar(diretorio: Path, prefixo: str = "") -> None:
        # Ordena pastas primeiro, depois ficheiros por ordem alfabética.
        entradas = sorted(diretorio.iterdir(), key=lambda p: (not p.is_dir(), p.name))
        for indice, entrada in enumerate(entradas):
            ultimo = indice == len(entradas) - 1
            conector = "└── " if ultimo else "├── "
            print(prefixo + conector + entrada.name + ("/" if entrada.is_dir() else ""))
            if entrada.is_dir():
                caminhar(entrada, prefixo + ("    " if ultimo else "│   "))

    caminhar(raiz)


# ------------------------------------------------------------------
# CLI — mista: aceita argumentos na linha de comandos e pergunta
# interativamente apenas o que faltar (exceto se for passado `-y`).
# ------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="urze",
        description="Forja o esqueleto completo de um projeto Python desktop (GTK3 + Debian).",
        epilog="Exemplos:\n"
               "  python3 urze.py OpenDWFx\n"
               "  python3 urze.py OpenDWFx --desc-file descricao.txt\n"
               "  python3 urze.py ferramenta --desc \"Uma ferramenta GTK\"\n"
               "  python3 urze.py                # interativo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("nome", nargs="?", help="nome do projeto (ex.: OpenDWFx ou meu-app); perguntado se faltar")
    parser.add_argument("--desc", help="descrição curta (ou caminho para ficheiro .txt/.md)")
    parser.add_argument("--desc-file", help="ficheiro de texto de onde ler a descrição do projeto")
    parser.add_argument("--nome-visivel", help="nome apresentável (omissão: derivado do nome)")
    parser.add_argument("--autor", default=AUTOR_PADRAO, help="autor dos cabeçalhos")
    parser.add_argument("--github", default=GITHUB_PADRAO, help="endereço GitHub")
    parser.add_argument("--dest", default=".", help="diretório onde criar <nome>/ (omissão: atual)")
    parser.add_argument("-y", "--sem-interativo", action="store_true", help="não perguntar; usa as omissões")
    args = parser.parse_args(argv)

    nao_interativo = args.sem_interativo
    autor = sanitizar_texto_curto(args.autor, AUTOR_PADRAO)
    github = args.github.strip().rstrip("/") or GITHUB_PADRAO

    # 1. Obter e normalizar o nome do projeto (pasta, dist e pkg)
    bruto = args.nome
    if bruto is None:
        if nao_interativo or not sys.stdin.isatty():
            parser.error("falta o nome do projeto (corre sem -y num terminal, ou passa o nome)")
        bruto = perguntar("Nome do projeto (ex.: OpenDWFx ou meu-app)", "meu-app", nao_interativo=nao_interativo)
        if not bruto:
            parser.error("é necessário um nome de projeto")

    # Se o utilizador passou um caminho (ex.: /home/paulo/Projetos/2-Apps/OpenDWFx),
    # separa o diretório pai para `dest_base` e o nome final para `bruto`.
    dest_base = Path(args.dest).expanduser().resolve()
    caminho_bruto = Path(bruto).expanduser()
    if len(caminho_bruto.parts) > 1:
        if args.dest == ".":
            dest_base = caminho_bruto.resolve().parent
        bruto = caminho_bruto.name

    pasta, dist, pkg = normalizar(bruto, nao_interativo=nao_interativo)

    # 2. Derivar IDs, nome de classe, nome visível e descrição (texto ou ficheiro)
    appid = construir_appid(autor, pkg)
    # Se o nome da pasta já tiver maiúsculas (ex.: OpenDWFx), preserva-as para a classe e nome visível
    if any(c.isupper() for c in pasta):
        classe = re.sub(r"[^A-Za-z0-9]", "", pasta)
        visivel_omissao = re.sub(r"[-_]+", " ", pasta)
    else:
        classe = "".join(parte.capitalize() for parte in pkg.split("_"))
        visivel_omissao = " ".join(parte.capitalize() for parte in dist.split("-"))

    visivel_bruto = args.nome_visivel or perguntar(
        "Nome apresentável", visivel_omissao, nao_interativo=nao_interativo
    )
    visivel = sanitizar_texto_curto(visivel_bruto, visivel_omissao)

    desc_omissao = f"{visivel} — aplicação desktop em Python/GTK3"
    desc, desc_longa = carregar_descricao(
        args.desc, args.desc_file, desc_omissao, visivel, nao_interativo
    )

    # 3. Construir o contexto da geração
    ctx = ContextoProjeto(
        pasta=pasta,
        dist=dist,
        pkg=pkg,
        appid=appid,
        classe=classe,
        visivel=visivel,
        desc=desc,
        desc_longa=desc_longa,
        autor=autor,
        github=github,
        nao_interativo=nao_interativo,
    )

    # 4. Verificar diretório de destino (se já existir, não o recria — reutiliza-o)
    raiz = dest_base / pasta
    if raiz.exists():
        print(f"  [info] Pasta '{raiz}' já existe — a utilizar a pasta existente.")
    else:
        raiz.mkdir(parents=True, exist_ok=True)

    gerar(ctx, raiz)
    mostrar_arvore(raiz)
    print("\nEsqueleto pronto. Próximos passos:")
    print(f"  cd {raiz}")
    print("  ./install.sh                # instala ambiente + atalho (ou ./scripts/install.py)")
    print("  ./run                       # abre a janela de exemplo")
    print("  git init && git add -A && git commit -m 'Versão inicial'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
