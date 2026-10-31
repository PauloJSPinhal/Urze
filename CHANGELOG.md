# Registo de Alterações (Changelog)

Todas as alterações relevantes a este projeto serão documentadas neste ficheiro.  
O formato baseia-se em [Keep a Changelog](https://keepachangelog.com/pt-PT/1.0.0/).

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