#!/usr/bin/env bash
# =========================================================================
# Projeto : urze
# Ficheiro: install.sh — instala o comando `urze` em ~/.local/bin (ou /usr/local/bin)
# Autor   : PauloJSPinhal
# Criado  : 2026-11-08
# GitHub  : https://github.com/PauloJSPinhal
# =========================================================================
# Uso:
#   ./install.sh            # instala para o utilizador atual em ~/.local/bin/urze
#   ./install.sh --system   # instala globalmente em /usr/local/bin/urze (pede sudo)

set -euo pipefail
cd "$(dirname "$0")"

ORIGEM="$PWD/urze.py"
if [[ ! -f "$ORIGEM" ]]; then
    echo "  [ERRO] Não encontrei urze.py em $PWD" >&2
    exit 1
fi

if [[ "${1:-}" == "--system" ]]; then
    DEST_DIR="/usr/local/bin"
    DEST="$DEST_DIR/urze"
    echo "[urze] A instalar globalmente em $DEST..."
    if [[ $EUID -ne 0 ]]; then
        sudo install -m 755 "$ORIGEM" "$DEST"
    else
        install -m 755 "$ORIGEM" "$DEST"
    fi
else
    DEST_DIR="$HOME/.local/bin"
    DEST="$DEST_DIR/urze"
    echo "[urze] A instalar para o utilizador em $DEST..."
    mkdir -p "$DEST_DIR"
    install -m 755 "$ORIGEM" "$DEST"

    if [[ ":$PATH:" != *":$DEST_DIR:"* ]]; then
        echo "  [aviso] $DEST_DIR ainda não está no teu PATH."
        echo "          Adiciona ao teu ~/.bashrc:"
        echo "          export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
fi

echo "  [ok]   Instalado com sucesso: $DEST"
echo "         Já podes criar projetos em qualquer pasta correndo:  urze <nome-do-projeto>"
