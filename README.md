# urze

> Gerador de esqueletos (*scaffolding*) de projetos desktop Python 3 + GTK3 para Debian/GNU Linux (com suporte a `.deb`, `AppImage`, `Windows` e `macOS`).

`urze` enraíza num único comando a estrutura completa para aplicações gráficas em Python + GTK3: *src layout*, empacotamento `hatchling`, integração PyGObject/GTK3, instalador em 4 fases e geração de pacotes nativos Debian (`.deb`), portáteis Linux (`.AppImage`), executáveis/instaladores para Windows (`--onedir` + `Inno Setup`) e instaladores Apple macOS (`.app` + `.dmg`).

Não requer dependências externas — funciona nativamente com o `python3` da biblioteca padrão num Debian limpo.

---

## Características

- **Stdlib-only:** Execução sem recorrer a `pip` ou módulos de terceiros.
- **Src Layout & PEP 621:** Empacotamento moderno via `pyproject.toml` com backend `hatchling`.
- **Instalador em 4 Fases (`scripts/install.py`):**
  1. *apt*: Valida e instala pacotes Debian necessários (com deteção automática de ambientes Flatpak).
  2. *venv*: Cria o ambiente virtual com `--system-site-packages` (essencial para aceder a `gi` e GTK3).
  3. *pip*: Instala a aplicação no venv em modo editável e sem isolamento de rede (`pip install --no-build-isolation -e .`).
  4. *check*: Validação com `pip check` e verificação de importação do GTK3.
- **Tematização Desacoplada:** Módulo `appearance` com alternância entre temas (sistema, claro e escuro) e seleção de fontes em tempo real via Pango/CSS (compatível com ambientes congelados PyInstaller).
- **Distribuição Multiplataforma Pronta:**
  - **Debian / Ubuntu (`.deb`):** `scripts/build_packages.sh`
  - **Linux Universal (`.AppImage`):** `scripts/build_appimage.sh`
  - **Windows (Modo Pasta `--onedir` + Instalador `Setup.exe`):** `scripts/build_windows.sh` (MSYS2 + PyInstaller + Inno Setup)
  - **Apple macOS (`.app` + Instalador `.dmg`):** `scripts/build_macos.sh` (Homebrew + PyInstaller + `hdiutil`)
  - **GitHub Actions CI/CD:** `.github/workflows/build.yml` constrói automaticamente os instaladores de Linux, Windows e macOS na nuvem.

---

## Requisitos

- Debian 11+ (ou derivados como Ubuntu 20.04+)
- Python 3.9+

---

## Instalação

Para instalar o comando `urze` no teu utilizador (`~/.local/bin/urze`):

```bash
./install.sh
```

Para instalar para todos os utilizadores do sistema (`/usr/local/bin/urze`):

```bash
./install.sh --system
```

Para desinstalar:

```bash
./uninstall.sh
```

> **Nota:** Certifica-te de que `~/.local/bin` está no teu `$PATH` (comum na maioria das distribuições Linux modernas).

---

## Utilização

Se instalaste em `~/.local/bin/urze`:

```bash
urze meu-app
```

Em alternativa, executando o script diretamente:

```bash
python3 urze.py meu-app
```

### Exemplos de Utilização

**Modo Interativo (pergunta dados em falta):**
```bash
urze
```

**Linha de Comandos direta com argumentos (ou descrição via ficheiro de texto):**
```bash
urze OpenDWFx --desc "Visualizador de ficheiros DWFx em GTK3"
# ou lendo a descrição a partir de um ficheiro de texto:
urze OpenDWFx --desc-file descricao.txt
```

**Modo Não Interativo (ideal para CI/Scripts):**
```bash
urze OpenDWFx -y
```

### Opções da CLI

| Opção | Descrição | Omissão |
| :--- | :--- | :--- |
| `nome` | Nome ou caminho do projeto (preserva maiúsculas na pasta, ex.: `OpenDWFx`) | Interativo |
| `--desc` | Descrição curta (ou caminho para ficheiro de texto `.txt`/`.md`) | `<Nome> — aplicação desktop...` |
| `--desc-file` | Ficheiro de texto de onde ler a descrição do projeto | `None` |
| `--nome-visivel` | Nome apresentável na interface | Derivado de `nome` |
| `--autor` | Autor nos cabeçalhos | `PauloJSPinhal` |
| `--github` | Endereço GitHub | `https://github.com/PauloJSPinhal` |
| `--dest` | Diretório de destino (se a pasta já existir, reutiliza-a e pergunta por ficheiro se escreve ou ignora) | `.` |
| `-y, --sem-interativo` | Não efetua perguntas (ignora ficheiros já existentes) | `False` |

---

## Estrutura Gerada

```text
meu-app/
├── install.sh                   # Instala ambiente (.venv) + comando e atalho no menu do utilizador
├── uninstall.sh                 # Remove atalho, comando e ambiente (.venv)
├── run                          # Arranque em desenvolvimento (.venv + python -m)
├── pyproject.toml               # Metadados, dependências e entry-points
├── requirements-apt.txt         # Dependências de sistema Debian
├── requirements.txt             # Lock file opcional
├── .gitignore                   # Ficheiros ignorados pelo Git
├── README.md                    # Apresentação da aplicação (esqueleto a preencher)
├── ARCHITECTURE.md              # Registo de módulos e vistas (esqueleto a preencher)
├── CONTRIBUTING.md              # Guia rápido de contribuição (esqueleto a preencher)
├── CHANGELOG.md                 # Histórico de versões (esqueleto a preencher)
├── SECURITY.md                  # Política de segurança (esqueleto a preencher)
├── LICENSE.md                   # Licença integral (GPL-3.0-or-later) + aviso de copyright
├── .github/workflows/
│   └── build.yml                # Cria automaticamente .deb, .AppImage, Setup.exe e .dmg no GitHub
├── docs/                        # Guias de ajuda em linguagem acessível para programar no projeto
│   ├── 1-para-que-serve-cada-pasta-e-ficheiro.md
│   ├── 2-como-funciona-o-instalador-e-o-arranque.md
│   ├── 3-onde-escrever-o-teu-codigo.md
│   ├── 4-como-mudar-cores-letra-e-icone.md
│   ├── 5-como-adicionar-extras-e-criar-instaladores.md
│   └── notas.md                 # Rascunho para ideias e tarefas
├── scripts/
│   ├── install.py               # Instalador em 4 fases + verificação (--check)
│   ├── build_packages.sh        # Cria debian/ e constrói o pacote .deb
│   ├── build_appimage.sh        # Constrói o ficheiro portátil .AppImage
│   ├── build_windows.sh         # Constrói a pasta (--onedir), .zip e Instalador Windows (.exe)
│   └── build_macos.sh           # Constrói a aplicação (.app) e Instalador Apple macOS (.dmg)
├── data/
│   ├── pt.paulojspinhal.meu_app.desktop       # Lançador do ambiente de trabalho
│   ├── pt.paulojspinhal.meu_app.metainfo.xml  # Metadados AppStream
│   └── icons/
│       ├── README.md                          # Guia para disposição dos ícones
│       └── scalable/apps/
│           └── pt.paulojspinhal.meu_app.svg   # Ícone vetorial de exemplo (hicolor)
├── tests/
│   └── test_smoke.py                          # Testes sem interface gráfica (inclui persistência XDG)
└── src/
    └── meu_app/
        ├── __init__.py          # __version__ (fonte única da versão)
        ├── __main__.py          # Suporte a python -m meu_app
        ├── main.py              # Janela de exemplo com controlos de tema
        ├── py.typed             # Marcador PEP 561
        ├── core/                # ModuloBase e contratos da aplicação
        ├── defaults/            # Configuração JSON e CSS dos temas
        ├── views/               # Componentes de interface
        └── modules/
            └── appearance/      # Aplicação dinâmica de temas e fontes
```

---

## Licença

GPL-3.0-or-later — ver [LICENSE.md](LICENSE.md).  
Autor: [PauloJSPinhal](https://github.com/PauloJSPinhal).