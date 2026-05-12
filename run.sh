#!/bin/zsh
cd "$(dirname "$0")"
[[ -f "$HOME/.zprofile" ]] && source "$HOME/.zprofile"
[[ -f "$HOME/.zshrc" ]]   && source "$HOME/.zshrc"
exec .venv/bin/python3 main.py
