# Registo de Alterações (Changelog)

Todas as alterações relevantes a este projeto serão documentadas neste ficheiro.  
O formato baseia-se em [Keep a Changelog](https://keepachangelog.com/pt-PT/1.0.0/).

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