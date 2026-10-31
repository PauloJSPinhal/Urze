# urze

> Gerador de esqueletos (*scaffolding*) de projetos desktop Python 3 + GTK3 para Debian/GNU Linux.

`urze` enraíza num único comando a estrutura completa para aplicações gráficas em Linux: *src layout*, empacotamento `hatchling`, integração PyGObject/GTK3, instalador em 4 fases e empacotamento nativo Debian (`.deb`).

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
- **Tematização Desacoplada:** Módulo `appearance` com alternância entre temas (sistema, claro e escuro) e seleção de fontes em tempo real via Pango/CSS.
- **Distribuição Pronta:** Lançador XDG (`.desktop`), metadados AppStream (`.metainfo.xml`) e script automatizado para gerar pacotes Debian (`scripts/build_packages.sh`).

---

## Requisitos

- Debian 11+ (ou derivados como Ubuntu 20.04+)
- Python 3.9+

---

## Instalação

Para utilizar o `urze` em qualquer terminal do teu utilizador, basta instalar o script em `~/.local/bin/`:

```bash
mkdir -p ~/.local/bin
install -m 755 urze.py ~/.local/bin/urze
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

**Linha de Comandos direta com argumentos:**
```bash
urze meu-app --desc "Editor de notas em GTK3" --nome-visivel "Meu App"
```

**Modo Não Interativo (ideal para CI/Scripts):**
```bash
urze meu-app -y
```

### Opções da CLI

| Opção | Descrição | Omissão |
| :--- | :--- | :--- |
| `nome` | Nome do projeto (ex.: `meu-app`) | Interativo |
| `--desc` | Descrição curta | `<Nome> — aplicação desktop...` |
| `--nome-visivel` | Nome apresentável na interface | Derivado de `nome` |
| `--autor` | Autor nos cabeçalhos | `PauloJSPinhal` |
| `--github` | Endereço GitHub | `https://github.com/PauloJSPinhal` |
| `--dest` | Diretório de destino | `.` |
| `-y, --sem-interativo` | Não efetua perguntas | `False` |

---

## Estrutura Gerada

```text
meu-app/
├── run                          # Arranque em desenvolvimento (.venv + python -m)
├── pyproject.toml               # Metadados, dependências e entry-points
├── requirements-apt.txt         # Dependências de sistema Debian
├── requirements.txt             # Lock file opcional
├── .gitignore                   # Ficheiros ignorados pelo Git
├── README.md                    # Documentação da aplicação criada
├── LICENSE                      # Licença integral (GPL-3.0-or-later)
├── docs/notas.md                # Registo de decisões técnicas
├── scripts/
│   ├── install.py               # Instalador em 4 fases + verificação (--check)
│   └── build_packages.sh        # Cria debian/ e constrói o pacote .deb
├── data/
│   ├── pt.paulojspinhal.meu_app.desktop       # Lançador do ambiente de trabalho
│   ├── pt.paulojspinhal.meu_app.metainfo.xml  # Metadados AppStream
│   └── icons/README.md                        # Guia para disposição dos ícones
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