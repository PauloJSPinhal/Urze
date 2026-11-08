# Registo de Alterações (Changelog)

Todas as alterações relevantes a este projeto serão documentadas neste ficheiro.  
O formato baseia-se em [Keep a Changelog](https://keepachangelog.com/pt-PT/1.0.0/).

## [0.1.3] - 2026-11-08

### Adicionado
- Scripts `install.sh` e `uninstall.sh` no próprio projeto `Urze` (para instalar/remover o comando `urze` em `~/.local/bin` ou `/usr/local/bin`) e também na raiz dos novos projetos gerados (executam `scripts/install.py` e instalam/removem o comando `~/.local/bin/<dist>`, ícone SVG e atalho `.desktop` no menu do utilizador).
- Suporte a nomes de pastas com maiúsculas (ex.: `OpenDWFx`), mantendo automaticamente o pacote Python (`src/opendwfx`) e o pacote Debian (`opendwfx`) em minúsculas.
- Reutilização segura de pastas existentes: se a pasta do projeto já existir, não falha nem a recria, perguntando ficheiro a ficheiro se deve escrever por cima ou ignorar (`[e]screver / [i]gnorar / [t]odos escrever / [I]gnorar todos`).
- Leitura da descrição do projeto a partir de ficheiro de texto (via `--desc-file FICHEIRO`, passando o caminho do ficheiro em `--desc`, ou escrevendo o caminho do ficheiro na pergunta interativa), preenchendo o resumo de 1 linha e a apresentação completa no `README.md`.
- Suporte à geração de pacotes portáteis **AppImage** para Linux através de `scripts/build_appimage.sh` (cria `AppDir`, script `AppRun` e descarrega `appimagetool` automaticamente se ausente).
- Suporte à geração de executáveis e instaladores para **Windows** em Modo Pasta (`--onedir`) + ZIP portátil + Instalador **Inno Setup** (`Setup-*.exe`) através de `scripts/build_windows.sh` (para MSYS2 MinGW64 + PyInstaller).
- Suporte à geração de aplicações (`.app`) e instaladores de disco (`.dmg`) para **Apple macOS** através de `scripts/build_macos.sh` (Homebrew + PyInstaller + `iconutil` + `hdiutil`).
- Geração automática de workflow **GitHub Actions** (`.github/workflows/build.yml`) para compilar e publicar na nuvem os instaladores de Linux (`.deb` + `.AppImage`), Windows (`Setup-*.exe` + `.zip`) e Apple macOS (`.dmg`) sem necessidade de máquinas Windows ou Mac locais.
- Guia `docs/5-como-adicionar-extras-e-criar-instaladores.md` atualizado com instruções passo a passo acessíveis para gerar `.deb`, `.AppImage`, `.exe` de Windows e `.dmg` de macOS.

### Corrigido
- `pyproject.toml`: adicionado `dev-mode-dirs = ["src"]` em `[tool.hatch.build.targets.wheel]` para que o `hatchling` crie um ficheiro `.pth` direto no `pip install --no-build-isolation -e .` sem depender do módulo externo `editables`.
- `scripts/install.py` (Fase 4): a verificação `pip check` filtra conflitos do próprio projeto (ignorando falsos positivos de pacotes globais do sistema Debian visíveis via `--system-site-packages`) e valida explicitamente a importação de `<pkg>`.

### Alterado
- `src/<pkg>/defaults/config.py`: `ficheiro_config()` passa a suportar nativamente o diretório `APPDATA` em Windows (`os.name == "nt"`) e `~/Library/Application Support` em macOS (`sys.platform == "darwin"`), mantendo `XDG_CONFIG_HOME` / `~/.config` em Linux.
- `src/<pkg>/modules/appearance/tema.py`: localização da pasta `defaults/` compatível com execução congelada pelo PyInstaller (`sys._MEIPASS`).

## [0.1.2] - 2026-10-31

### Adicionado
- Geração na raiz de modelos enxutos prontos a preencher ao longo do projeto: `README.md`, `LICENSE.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md` e `ARCHITECTURE.md`.
- Criação de 5 guias passo a passo em `docs/` escritos em linguagem acessível para iniciantes, com títulos autoexplicativos:
  - `docs/1-para-que-serve-cada-pasta-e-ficheiro.md`
  - `docs/2-como-funciona-o-instalador-e-o-arranque.md`
  - `docs/3-onde-escrever-o-teu-codigo.md`
  - `docs/4-como-mudar-cores-letra-e-icone.md`
  - `docs/5-como-adicionar-extras-e-criar-instalador-deb.md`
- Geração automática de ícone vetorial de exemplo (`data/icons/scalable/apps/<appid>.svg`) no tema `hicolor`.
- Suporte a cabeçalhos em comentário XML (`<!-- ... -->`) para ficheiros `.svg` em `estilo_para()`.

### Alterado
- Ficheiro de licença gerado passa a ser `LICENSE.md`, incluindo no rodapé o bloco de copyright personalizado com nome, descrição, ano e autor do projeto.
- `scripts/build_packages.sh` inclui automaticamente o ícone SVG gerado em `debian/<dist>.install` (`usr/share/icons/hicolor/scalable/apps/`).
- Guia `data/icons/README.md` e `docs/notas.md` atualizados para refletir a presença do ícone SVG funcional de origem.

## [0.1.1] - 2026-10-31

### Corrigido
- Formato do *Application ID* (`APPID`) corrigido para 3 segmentos em *reverse-DNS* (`pt.<autor>.<pkg>`), cumprindo os requisitos de validação do GLib/GTK3 (`Gio.Application.id_is_valid`).
- Extração e conversão dos operadores de versão (`>=`, `>>`, `<=`, `<<`, `=`) em `scripts/install.py` antes da chamada a `dpkg --compare-versions`.
- Reposição da preferência nativa do ambiente gráfico (`reset_property("gtk-application-prefer-dark-theme")`) quando o esquema `"sistema"` está ativo no módulo `appearance`.
- Inclusão do pacote `python3-all` na verificação de ferramentas de *build* em `scripts/build_packages.sh` para coincidir com o `Build-Depends` de `debian/control`.
- Sanitização de strings e escape XML/Pango (`__VISIVEL_XML__`, `__AUTOR_XML__`, `__DESC_XML__`) na interface GTK3 e nos metadados AppStream.
- Substituição de tokens em passagem única via expressão regular (`re.sub`), prevenindo colisões e substituições em cascata.

### Alterado
- Refatoração do estado global mutável de `urze.py` para a dataclass `ContextoProjeto`.
- Fase 3 de `scripts/install.py` passa a executar `pip install --no-build-isolation -e .` em conjunto com `python3-pip` e `python3-hatchling` em `requirements-apt.txt`, permitindo instalações locais sem acesso à internet.
- O token `__CLASSE__` passa a dar nome à classe principal da aplicação GTK3 (`<Classe>App`) em `src/<pkg>/main.py`.

### Adicionado
- Testes unitários de persistência XDG (`guardar_config`, `carregar_config` e recuperação perante JSON corrompido) em `tests/test_smoke.py`.
- Comentários explicativos detalhados em todo o código de `urze.py`.

## [0.1.0] - 2026-10-31

### Adicionado
- Versão inicial do gerador `urze.py`.
- Suporte a geração completa de arquitetura em *src layout*.
- Ficheiro `pyproject.toml` configurado para `hatchling` (PEP 621).
- Script `scripts/install.py` com ciclo de vida em 4 fases (`apt`, `venv`, `pip -e .` e `verificação`).
- Suporte à flag `--check` no instalador para integração contínua (CI).
- Módulo `appearance` para gestão de temas claro/escuro e injeção de fontes via Pango/CSS.
- Ficheiros de metadados para desktop: `.desktop` e AppStream `.metainfo.xml`.
- Script de automação de empacotamento Debian `scripts/build_packages.sh`.
- Documentação base (`README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`).