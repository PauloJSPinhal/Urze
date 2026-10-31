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
    --desc "texto"        descrição curta do projeto (uma frase)
    --nome-visivel "X"    nome apresentável (omissão: derivado do nome)
    --autor "NOME"        autor dos cabeçalhos (omissão: PauloJSPinhal)
    --github URL          endereço GitHub (omissão: https://github.com/PauloJSPinhal)
    --dest DIR            diretório onde criar <nome>/ (omissão: '.')
    -y, --sem-interativo  nunca perguntar; usa as omissões (para scripts/CI)

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
from pathlib import Path

# ------------------------------------------------------------------
# Estado global preenchido pelo main() antes de gerar os ficheiros.
# ------------------------------------------------------------------
AUTOR = "PauloJSPinhal"
GITHUB = "https://github.com/PauloJSPinhal"
DATA = datetime.date.today().isoformat()
DIST = ""        # nome PyPI/diretório, com traços:  meu-app
PKG = ""         # nome de import, com underscores: meu_app
APPID = ""       # id de aplicação:                 pt.meu-app
CLASSE = ""      # CamelCase:                       MeuApp
VISIVEL = ""     # nome apresentável:               Meu App
DESC = ""        # descrição curta sanitizada
NAO_INTERATIVO = False

TOKENS = {}      # substituição textual: __DIST__, __PKG__, …


def subst(texto):
    """Aplica todos os tokens ao texto de um template."""
    for chave, valor in TOKENS.items():
        texto = texto.replace(chave, valor)
    return texto


def cabec(ficheiro, papel, estilo="#"):
    """Bloco de cabeçalho em caixa, comum a todos os ficheiros gerados.

    Identifica (projeto, ficheiro), caracteriza (autor, data, github) e
    situa o ficheiro (papel) na estrutura do projeto.
    """
    linhas = [
        f"Projeto : {DIST}",
        f"Ficheiro: {ficheiro} — {papel}",
        f"Autor   : {AUTOR}",
        f"Criado  : {DATA}",
        f"GitHub  : {GITHUB}",
    ]
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


def perguntar(rotulo, omissao=""):
    """Pergunta interativa com valor por omissão (Enter aceita)."""
    if NAO_INTERATIVO or not sys.stdin.isatty():
        return omissao
    sugestao = f" [{omissao}]" if omissao else ""
    try:
        resposta = input(f"{rotulo}{sugestao}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return omissao
    return resposta or omissao


def normalizar(bruto):
    """Normaliza o nome do projeto para as três formas (dist, pkg).

    Convenção: PyPI/diretório com traços (meu-app), import com underscores
    (meu_app). Sugere a forma normalizada e permite corrigir.
    """
    dist = re.sub(r"[\s_]+", "-", bruto.strip().lower())
    dist = re.sub(r"-{2,}", "-", dist).strip("-")
    if not re.fullmatch(r"[a-z]([a-z0-9-]*[a-z0-9])?", dist):
        sys.exit(
            f"urze: nome inválido: {bruto!r}\n"
            "  usa minúsculas, dígitos e traços, começando por letra (ex.: 'meu-app')."
        )
    pkg = dist.replace("-", "_")
    if keyword.iskeyword(pkg):
        sys.exit(f"urze: {pkg!r} é uma palavra reservada do Python; escolhe outro nome.")
    if len(dist) > 40:
        sys.exit("urze: nome demasiado longo (máximo 40 caracteres).")
    if dist != bruto.strip() and not NAO_INTERATIVO and sys.stdin.isatty():
        confirmado = perguntar(f"Nome normalizado: {bruto!r} → {dist!r} (Enter confirma, ou escreve outro)", dist)
        if confirmado and confirmado != dist:
            return normalizar(confirmado)
    return dist, pkg


# ------------------------------------------------------------------
# TEMPLATES — ficheiros de topo do projeto gerado.
# Cada função devolve o corpo (sem o cabeçalho em caixa, que é
# acrescentado pela rotina de escrita).
# ------------------------------------------------------------------


def t_run():
    return '''\
#!/usr/bin/env bash
# Script de arranque em desenvolvimento: executa o pacote dentro do venv,
# nunca contra o Python do sistema. É o equivalente de `python -m __PKG__`
# com o ambiente certo garantido.
#
# Porqui -m e não src/__PKG__/main.py: o src layout exige que o pacote
# esteja importável (o install.py faz `pip install -e .` no venv); correr
# o ficheiro diretamente quebraria os imports relativos do pacote.
set -euo pipefail
cd "$(dirname "$0")"

PY=".venv/bin/python"
if [[ ! -x "$PY" ]]; then
    echo "Ambiente não configurado. Corre primeiro: ./scripts/install.py" >&2
    exit 1
fi

exec "$PY" -m __PKG__ "$@"
'''


def t_pyproject():
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
'''


def t_requirements():
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


def t_requirements_apt():
    return '''\
# Dependências de SISTEMA (Debian/GNU Linux) do projeto.
#
# É a fonte única para três consumidores:
#   1. scripts/install.py       — verifica e instala o que falta (fase 1);
#   2. scripts/build_packages.sh — gera a linha Depends: do debian/control;
#   3. CI (--check)             — falha se algo faltar, sem instalar.
#
# Sintaxe à la debian/control:  nome-do-pacote (>= versão)  — a restrição
# de versão é opcional e validada pelo install.py com dpkg.
# No Depends: gerado, as restrições ficam sem espaços (aceite pelo dpkg).
#
# Nota: em Flatpak esta lista é ignorada (as libs vêm do runtime);
# o install.py deteta FLATPAK_ID e salta a fase apt.

python3-venv            # cria o .venv — tem de vir antes da fase 2
python3-gi              # PyGObject: torna o GTK acessível como `import gi`
python3-gi-cairo        # ponte PyGObject ↔ cairo
gir1.2-gtk-3.0          # GTK3 (introspecção)
gir1.2-gdkpixbuf-2.0    # carregamento de imagens
desktop-file-utils      # validação/instalação do lançador .desktop
'''


def t_gitignore():
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

# Empacotamento Debian (gerado por scripts/build_packages.sh)
debian/.debhelper/
debian/files
debian/*.log
debian/*.substvars
debian/debhelper-build-stamp
debian/__DIST__/
*.deb
*.changes
*.buildinfo
'''


def t_readme():
    return '''\
# __VISIVEL__

> __DESC__

Aplicação desktop em Python 3 + GTK3, pensada para Debian/GNU Linux.
Esqueleto criado com **urze** — substitui esta descrição pela do teu projeto.

## Requisitos

- Debian 11+ (ou derivado) com Python 3.9+
- Pacotes de sistema listados em `requirements-apt.txt` (GTK3 via PyGObject)

## Instalação (uma só passada)

    ./scripts/install.py

Faz tudo, por fases: 1) pacotes apt que faltam (uma chamada `apt-get`
agregada, sudo só aí) → 2) cria `.venv` com `--system-site-packages`
(necessário para o `import gi` funcionar) → 3) `pip install -e .` →
4) verificação (`pip check` + GTK acessível).

Verificação sem alterar nada — para CI ou auditoria:

    ./scripts/install.py --check

## Uso

    ./run

O `run` executa `.venv/bin/python -m __PKG__`. O mesmo código é alcançado,
sem venv, pelo entry point `__DIST__` instalado pelo `.deb` (ou `pip install .`).

## Tematização (módulo appearance)

- `src/__PKG__/defaults/tema_escuro.css` e `tema_claro.css` — edita à vontade;
- esquemas de cores: `sistema` (segue o tema do ambiente), `preto`, `branco`;
- fonte escolhível num `Gtk.FontButton`, injetada em CSS via Pango;
- escolhas guardadas em `~/.config/__PKG__/aparencia.json`.

API para usar noutros módulos/vistas:

    from __PKG__.modules.appearance import aplicar_tema
    aplicar_tema(self, self.config)

## Estrutura

```
__DIST__/
├── run                          # arranque em desenvolvimento (venv + -m)
├── pyproject.toml               # fonte única: metadados + deps + entry point
├── requirements.txt             # lock Python gerado (opcional)
├── requirements-apt.txt         # fonte única das deps de sistema Debian
├── scripts/
│   ├── install.py               # 4 fases: apt → venv → pip → verificação
│   └── build_packages.sh        # gera debian/ e constrói o .deb
├── data/                        # lançador .desktop, metadados AppStream, ícones
├── docs/notas.md                # decisões e notas de desenvolvimento
├── tests/test_smoke.py          # testes que correm sem GTK
└── src/__PKG__/
    ├── __init__.py              # __version__ — fonte única da versão
    ├── __main__.py              # python -m __PKG__
    ├── main.py                  # janela de exemplo com tematização
    ├── core/                    # contratos partilhados (ModuloBase)
    ├── defaults/                # CSS dos temas + config por omissão
    ├── views/                   # janelas e componentes da interface
    └── modules/
        └── appearance/          # API: aplicar_tema(janela, config)
```

## Testes

    ./scripts/install.py && .venv/bin/python -m pytest -q
    # ou, sem venv:  PYTHONPATH=src python3 -m pytest -q

## Empacotamento Debian (opcional)

    ./scripts/build_packages.sh

Gera `debian/` a partir de `requirements-apt.txt` (Depends:) e constrói
`../__DIST___<versão>_<arquitetura>.deb`. Requer os pacotes de build
listados no cabeçalho do script.

## Convenção de módulos

Cada módulo vive em `src/__PKG__/modules/<nome>/`:

- API pública no `__init__.py` — pequena, estática, copiável entre projetos;
- implementação em ficheiros internos (`tema.py`, `fonte.py`, …);
- valores por omissão editáveis em `src/__PKG__/defaults/`;
- quando precisa de ciclo de vida, herda de `__PKG__.core.ModuloBase`.

## Licença

GPL-3.0-or-later — ver `LICENSE`. Autor: __AUTOR__ (__GITHUB__).
'''


def t_notas():
    return '''\
# Notas de desenvolvimento

Espaço livre para decisões, ideias e registos de trabalho do projeto.
Sugestão de disciplina: uma entrada por decisão, com data e porquê.

## Decisões

- __DATA__ — Esqueleto criado com urze: src layout, pyproject como fonte
  única, dependências de sistema em requirements-apt.txt, install.py em 4 fases,
  GTK3 com módulo appearance para tematização.

## Ideias

- (nada por agora)

## Tarefas

- [ ] Substituir o exemplo do main.py pela primeira funcionalidade real
- [ ] Adicionar ícones em data/icons/ (ver data/icons/README.md)
- [ ] Registar o projeto no README com capturas de ecrã
'''


# ------------------------------------------------------------------
# TEMPLATES — data/ (lançador, AppStream, ícones).
# ------------------------------------------------------------------


def t_desktop():
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


def t_metainfo():
    return '''\
<?xml version="1.0" encoding="UTF-8"?>
<!-- Metadados AppStream do __VISIVEL__: alimentam os "Software Centers"
     (GNOME Software, Discover); validar com appstreamcli validate.
     O <id> tem de coincidir com o nome do lançador (__APPID__.desktop). -->
<component type="desktop-application">
  <id>__APPID__</id>
  <metadata_license>FSFAP</metadata_license>
  <project_license>GPL-3.0-or-later</project_license>
  <developer_name>__AUTOR__</developer_name>
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


def t_icons_readme():
    return '''\
# Ícones do __VISIVEL__

Pasta destinada aos ícones da aplicação. Enquanto estiver vazia, o
lançador mostra um ícone genérico do ambiente — funciona, mas é feio.

## Layout recomendado (tema hicolor)

    16x16/apps/__APPID__.png, 22x22/…, 24x24/…, 32x32/…,
    48x48/…, 64x64/…, 128x128/apps/__APPID__.png
    scalable/apps/__APPID__.svg          ← o ideal: um SVG resolve tudo

## Para completar

1. Coloca aqui os ficheiros com o nome `__APPID__.*`;
2. Acrescenta as linhas correspondentes a `debian/__DIST__.install`
   (gerado por scripts/build_packages.sh), por exemplo:

       data/icons/scalable/apps/__APPID__.svg usr/share/icons/hicolor/scalable/apps/

3. No .deb, o dh_icons actualiza as caches de ícones automaticamente.
'''


# ------------------------------------------------------------------
# TEMPLATES — pacote Python (src/__PKG__/…).
# ------------------------------------------------------------------


def t_init():
    return '''\
# Ficha do pacote: docstring e __version__.
# A versão vive APENAS aqui — o hatchling extrai-a daqui para o
# pyproject.toml ([tool.hatch.version]); não a repitas noutro sítio.

"""__VISIVEL__ — __DESC__."""

__version__ = "0.1.0"
'''


def t_main_modulo():
    return '''\
# Ponto de entrada de `python -m __PKG__` — é assim que o ./run arranca.
# Apenas delega no main() de main.py; sem lógica própria.

from __PKG__.main import main

if __name__ == "__main__":
    main()
'''


def t_main():
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
            "<span size='x-large' weight='bold'>__VISIVEL__</span>\\n"
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


class Aplicacao(Gtk.Application):
    """Aplicação GTK3 — id __APPID__ (ver data/__APPID__.desktop)."""

    def __init__(self):
        super().__init__(application_id="__APPID__")

    def do_activate(self):
        Janela(self, carregar_config()).show_all()


def main():
    """Ponto de entrada — chamado por __main__.py e pelo entry point __DIST__."""
    GLib.set_application_name("__VISIVEL__")
    Aplicacao().run(sys.argv)
'''


def t_core():
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


def t_views():
    return '''\
# Vistas: janelas, diálogos e widgets compostos da interface.
# Convenção: um ficheiro por componente; a lógica de negócio vive em
# modules/, a apresentação aqui. O main.py é a janela principal; quando
# a interface crescer, migra-a para cá (ex.: views/janela_principal.py).
'''


def t_config():
    return '''\
# Configuração de aparência do utilizador: valores por omissão, validação
# e persistência em ~/.config/__PKG__/aparencia.json (respeita o
# XDG_CONFIG_HOME). Os esquemas disponíveis são fixos — "sistema", "preto",
# "branco" — e os CSS correspondentes vivem neste mesmo diretório.

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

ESQUEMAS = ("sistema", "preto", "branco")


@dataclass
class ConfigAparencia:
    """Estado da aparência: esquema de cores e fonte do utilizador."""

    esquema_cores: str = "sistema"   # "sistema" | "preto" | "branco"
    fonte: str = ""                  # "" = fonte do tema; ex.: "Noto Sans 11"


def ficheiro_config() -> Path:
    """Caminho do JSON de configuração, segundo o XDG Base Directory."""
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "__PKG__" / "aparencia.json"


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


def t_css_escuro():
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


def t_css_claro():
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


def t_appearance_init():
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

from ..defaults.config import ConfigAparencia
from .fonte import Fonte
from .tema import Tema

__all__ = ["Tema", "Fonte", "aplicar_tema"]


def aplicar_tema(janela: Gtk.Window, config: ConfigAparencia) -> None:
    """Aplica ao ecrã de `janela` o esquema de cores e a fonte de `config`."""
    Tema.aplicar(config.esquema_cores, Fonte.css_da_fonte(config.fonte))
'''


def t_tema():
    return '''\
# Esquemas de cores via CssProvider (GTK3 clássico).
#
# Funcionamento: um único provider é registado no ecrã; a cada mudança,
# o provider anterior é removido antes de o novo ser aplicado (evita
# acumulação de providers e conflitos de prioridade). O modo "sistema"
# não aplica CSS nenhum — deixa o tema do ambiente mandar; "preto" aplica
# o tema escuro e liga gtk-application-prefer-dark-theme; "branco" aplica
# o tema claro e desliga-a.

import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk

DIRETORIO_PADRAO = Path(__file__).resolve().parents[2] / "defaults"
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
        if Tema._provider is not None:
            Gtk.StyleContext.remove_provider_for_screen(
                Gdk.Screen.get_default(), Tema._provider
            )
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
        Gtk.Settings.get_default().set_property(
            "gtk-application-prefer-dark-theme", esquema == "preto"
        )
'''


def t_fonte():
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
            propriedades.append(f'font-family: "{familia}";')

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


def t_test_smoke():
    return '''\
# Testes de fumo: correm SEM GTK (não importam gi), para servirem de base
# a CI mínimo. Testes de interface, se existirem, vivem em ficheiros
# próprios e correm só onde haja servidor gráfico.

import pytest

import __PKG__
from __PKG__.core import ModuloBase
from __PKG__.defaults.config import ESQUEMAS, ConfigAparencia


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
'''


# ------------------------------------------------------------------
# TEMPLATES — scripts/ (instalador e empacotamento Debian).
# ------------------------------------------------------------------


def t_install():
    return '''\
#!/usr/bin/env python3
# Instalador do projeto — prepara tudo num sistema Debian, em 4 fases:
#   1. apt  — valida requirements-apt.txt e instala o que falta
#             (uma única chamada apt-get agregada; sudo só nesta fase;
#             saltada dentro de Flatpak — detetado por FLATPAK_ID);
#   2. venv — cria .venv com --system-site-packages, sem o qual o
#             `import gi` não funciona dentro do venv;
#   3. pip  — instala o próprio projeto: .venv/bin/pip install -e .
#   4. verificação — pip check + GTK3 acessível via gi.
#
# Modo de verificação (read-only, para CI):
#   ./scripts/install.py --check   → sai com código 1 se algo faltar.
#
# Idempotente: pode ser corrido quantas vezes for preciso.

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VENV = RAIZ / ".venv"
REQ_APT = RAIZ / "requirements-apt.txt"
DIST = "__DIST__"


def ok(msg):
    print(f"  [ok]    {msg}")


def aviso(msg):
    print(f"  [aviso] {msg}")


def erro(msg):
    print(f"  [ERRO]  {msg}", file=sys.stderr)


# --- fase 1: pacotes de sistema --------------------------------------
def ler_requisitos_apt():
    """requirements-apt.txt → [(nome, versão_mínima|None)], sem comentários."""
    requisitos = []
    for linha in REQ_APT.read_text(encoding="utf-8").splitlines():
        linha = linha.split("#", 1)[0].strip()
        if not linha:
            continue
        nome, _, resto = linha.partition("(")
        versao = resto.strip().rstrip(")").strip() or None
        requisitos.append((nome.strip(), versao))
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


def versao_suficiente(instalada, minima):
    """Compara versões com o dpkg (mesma semântica do debian/control)."""
    if not minima:
        return True
    try:
        return subprocess.run(
            ["dpkg", "--compare-versions", instalada, "ge", minima],
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
    for nome, minima in ler_requisitos_apt():
        instalado, versao = estado_pacote(nome)
        if instalado is None:
            erro("dpkg-query indisponível — isto não parece ser um sistema Debian.")
            return False
        if not instalado:
            faltantes.append(nome)
            aviso(f"ausente: {nome}")
        elif not versao_suficiente(versao, minima):
            faltantes.append(nome)
            aviso(f"desatualizado: {nome} {versao} (mínimo {minima})")
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
            ok(f"pacote {DIST} instalado no venv (modo editável).")
            return True
        erro(f"pacote {DIST} não instalado no venv.")
        return False
    return subprocess.run(
        [str(python), "-m", "pip", "install", "-e", "."], cwd=RAIZ
    ).returncode == 0


# --- fase 4: verificação -----------------------------------------------
def fase_verificar(verificar):
    """Fase 4 — pip check + o GTK3 tem de ser importável no venv."""
    python = VENV / "bin" / "python"
    if not python.exists():
        erro("venv ausente — nada a verificar.")
        return False

    em_ordem = True
    resultado = subprocess.run(
        [str(python), "-m", "pip", "check"], capture_output=True, text=True
    )
    if resultado.returncode == 0:
        ok("pip check: dependências Python consistentes.")
    else:
        erro(f"pip check: {(resultado.stdout or resultado.stderr).strip()}")
        em_ordem = False

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


def t_build():
    return r'''\
#!/usr/bin/env bash
# Empacotamento Debian: gera debian/ a partir de requirements-apt.txt
# (Depends:) e do pyproject.toml, e constrói o .deb com o pybuild.
#
# Requer (verificado em baixo): debhelper, dh-python,
#   pybuild-plugin-pyproject, python3-hatchling, build-essential.
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
for pacote in debhelper dh-python pybuild-plugin-pyproject python3-hatchling build-essential; do
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

# Ficheiros extra do pacote binário (desktop + metainfo; ícones: ver data/icons/README.md)
cat > "debian/${DIST}.install" <<FIM
data/__APPID__.desktop usr/share/applications/
data/__APPID__.metainfo.xml usr/share/metainfo/
FIM

echo "3.0 (native)" > debian/source/format

dpkg-buildpackage -us -uc -b
echo
echo ".deb construído em: $(dirname "$PWD")/"
'''


# ------------------------------------------------------------------
# ESCRITA — registry, cabeçalhos por tipo e LICENSE.
# ------------------------------------------------------------------

# (caminho, papel, função-geradora, executável). gerador None = ficheiro
# vazio de protocolo (py.typed, PEP 561) — sem cabeçalho por ser marcador.
FICHEIROS = [
    ("run", "arranque em desenvolvimento (venv + python -m)", t_run, True),
    ("pyproject.toml", "fonte única de metadados e dependências Python", t_pyproject, False),
    ("requirements.txt", "lock Python gerado (opcional)", t_requirements, False),
    ("requirements-apt.txt", "dependências de sistema Debian", t_requirements_apt, False),
    (".gitignore", "artefactos locais a não versionar", t_gitignore, False),
    ("README.md", "documentação principal", t_readme, False),
    ("docs/notas.md", "notas de desenvolvimento", t_notas, False),
    ("data/__APPID__.desktop", "lançador do ambiente de trabalho", t_desktop, False),
    ("data/__APPID__.metainfo.xml", "metadados AppStream", t_metainfo, False),
    ("data/icons/README.md", "guia dos ícones", t_icons_readme, False),
    ("scripts/install.py", "instalador em 4 fases + modo --check", t_install, True),
    ("scripts/build_packages.sh", "empacotamento Debian (.deb)", t_build, True),
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


def estilo_para(relativo):
    """Estilo do cabeçalho adequado ao tipo de ficheiro."""
    if relativo.endswith(".css"):
        return "css"
    if relativo.endswith(".md") or relativo.endswith(".xml"):
        return "html"
    return "#"


def escrever(raiz, relativo, papel, corpo, executavel):
    """Escreve um ficheiro com o cabeçalho em caixa (após o shebang, se houver)."""
    alvo = raiz / relativo
    alvo.parent.mkdir(parents=True, exist_ok=True)
    conteudo = subst(corpo).lstrip("\n")
    if conteudo.startswith("#!") or conteudo.startswith("<?xml"):
        # shebang e declaração XML têm de ficar na primeira linha — o
        # cabeçalho em caixa vai logo a seguir.
        primeira, _, resto = conteudo.partition("\n")
        conteudo = primeira + "\n" + cabec(Path(relativo).name, papel, estilo_para(relativo)) + resto
    else:
        conteudo = cabec(Path(relativo).name, papel, estilo_para(relativo)) + conteudo
    alvo.write_text(conteudo, encoding="utf-8")
    if executavel:
        alvo.chmod(0o755)


def escrever_licenca(raiz):
    """LICENSE com o texto integral da GPL-3.0 (fidelidade legal: sem cabeçalho)."""
    texto = ""
    local = Path("/usr/share/common-licenses/GPL-3")
    if local.exists():
        texto = local.read_text(encoding="utf-8", errors="replace")
    else:
        try:
            import urllib.request
            with urllib.request.urlopen("https://www.gnu.org/licenses/gpl-3.0.txt", timeout=15) as r:
                texto = r.read().decode("utf-8")
        except OSError:
            texto = ""

    alvo = raiz / "LICENSE"
    if texto:
        alvo.write_text(texto, encoding="utf-8")
    else:
        # Texto plano, sem moldura ou cabeçalho decorativo
        alvo.write_text(
            "GNU GENERAL PUBLIC LICENSE\n"
            "Versão 3.0 indisponível localmente e offline.\n"
            "Descarrega o texto integral para este ficheiro a partir de:\n"
            "https://www.gnu.org/licenses/gpl-3.0.txt\n",
            encoding="utf-8",
        )
        print("  [aviso] LICENSE: texto da GPL-3.0 indisponível localmente e online.")


def gerar(raiz):
    """Escreve todos os ficheiros do esqueleto."""
    for relativo, papel, gerador, executavel in FICHEIROS:
        relativo = subst(relativo)
        if gerador is None:
            (raiz / relativo).parent.mkdir(parents=True, exist_ok=True)
            (raiz / relativo).write_text("", encoding="utf-8")
            continue
        escrever(raiz, relativo, papel, gerador(), executavel)
    escrever_licenca(raiz)


def mostrar_arvore(raiz):
    """Imprime a árvore do que foi criado."""
    print(f"\n{raiz.name}/")

    def caminhar(diretorio, prefixo=""):
        entradas = sorted(diretorio.iterdir(), key=lambda p: (not p.is_dir(), p.name))
        for indice, entrada in enumerate(entradas):
            ultimo = indice == len(entradas) - 1
            conector = "└── " if ultimo else "├── "
            print(prefixo + conector + entrada.name + ("/" if entrada.is_dir() else ""))
            if entrada.is_dir():
                caminhar(entrada, prefixo + ("    " if ultimo else "│   "))

    caminhar(raiz)


# ------------------------------------------------------------------
# CLI — mista: flags na linha de comandos, interativo para o que faltar.
# ------------------------------------------------------------------


def main(argv=None):
    global NAO_INTERATIVO, AUTOR, GITHUB, DATA, DIST, PKG, APPID, CLASSE, VISIVEL, DESC

    parser = argparse.ArgumentParser(
        prog="urze",
        description="Forja o esqueleto completo de um projeto Python desktop (GTK3 + Debian).",
        epilog="Exemplos:\n"
               "  python3 urze.py meu-app\n"
               "  python3 urze.py ferramenta --desc \"Uma ferramenta GTK\"\n"
               "  python3 urze.py                # interativo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("nome", nargs="?", help="nome do projeto (ex.: meu-app); perguntado se faltar")
    parser.add_argument("--desc", help="descrição curta (uma frase)")
    parser.add_argument("--nome-visivel", help="nome apresentável (omissão: derivado do nome)")
    parser.add_argument("--autor", default=AUTOR, help="autor dos cabeçalhos")
    parser.add_argument("--github", default=GITHUB, help="endereço GitHub")
    parser.add_argument("--dest", default=".", help="diretório onde criar <nome>/ (omissão: atual)")
    parser.add_argument("-y", "--sem-interativo", action="store_true", help="não perguntar; usa as omissões")
    args = parser.parse_args(argv)

    NAO_INTERATIVO = args.sem_interativo
    AUTOR = args.autor.strip() or AUTOR
    GITHUB = (args.github.strip().rstrip("/") or GITHUB)
    DATA = datetime.date.today().isoformat()

    bruto = args.nome
    if bruto is None:
        if NAO_INTERATIVO or not sys.stdin.isatty():
            parser.error("falta o nome do projeto (corre sem -y num terminal, ou passa o nome)")
        bruto = perguntar("Nome do projeto (ex.: meu-app)", "meu-app")
        if not bruto:
            parser.error("é necessário um nome de projeto")

    DIST, PKG = normalizar(bruto)
    APPID = f"pt.{DIST}"
    CLASSE = "".join(parte.capitalize() for parte in PKG.split("_"))
    VISIVEL = args.nome_visivel or perguntar(
        "Nome apresentável", " ".join(parte.capitalize() for parte in DIST.split("-"))
    )
    DESC = args.desc or perguntar("Descrição curta", f"{VISIVEL} — aplicação desktop em Python/GTK3")
    DESC = re.sub(r"\s+", " ", DESC.replace('"', "'")).strip() or VISIVEL

    TOKENS.update({
        "__DIST__": DIST,
        "__PKG__": PKG,
        "__APPID__": APPID,
        "__CLASSE__": CLASSE,
        "__VISIVEL__": VISIVEL,
        "__DESC__": DESC,
        "__DESC_XML__": xml.sax.saxutils.escape(DESC),
        "__VISIVEL_XML__": xml.sax.saxutils.escape(VISIVEL),
        "__AUTOR__": AUTOR,
        "__GITHUB__": GITHUB,
        "__DATA__": DATA,
    })

    raiz = Path(args.dest).resolve() / DIST
    if raiz.exists():
        print(f"urze: {raiz} já existe — escolhe outro nome ou --dest.", file=sys.stderr)
        return 2

    gerar(raiz)
    mostrar_arvore(raiz)
    print("\nEsqueleto criado. Próximos passos:")
    print(f"  cd {raiz}")
    print("  ./scripts/install.py        # apt → venv → pip → verificação")
    print("  ./run                       # abre a janela de exemplo")
    print("  git init && git add -A && git commit -m 'Versão inicial'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
