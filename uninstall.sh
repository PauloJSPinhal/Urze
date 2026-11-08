#!/usr/bin/env bash
# =========================================================================
# Projeto : urze
# Ficheiro: uninstall.sh — remove o comando `urze` instalado no sistema
# Autor   : PauloJSPinhal
# Criado  : 2026-11-08
# GitHub  : https://github.com/PauloJSPinhal
# =========================================================================
# Uso:
#   ./uninstall.sh            # remove ~/.local/bin/urze
#   ./uninstall.sh --system   # remove /usr/local/bin/urze (pede sudo)

set -euo pipefail

REMOVIDO=0

if [[ "${1:-}" == "--system" ]]; then
    ALVO="/usr/local/bin/urze"
    if [[ -f "$ALVO" ]]; then
        echo "[urze] A remover $ALVO..."
        if [[ $EUID -ne 0 ]]; then
            sudo rm -f "$ALVO"
        else
            rm -f "$ALVO"
        fi
        echo "  [ok]   Removido: $ALVO"
        REMOVIDO=1
    fi
else
    ALVO="$HOME/.local/bin/urze"
    if [[ -f "$ALVO" ]]; then
        rm -f "$ALVO"
        echo "  [ok]   Removido: $ALVO"
        REMOVIDO=1
    fi
fi

if [[ $REMOVIDO -eq 0 ]]; then
    echo "  [info] O comando 'urze' não estava instalado em $ALVO."
fi
