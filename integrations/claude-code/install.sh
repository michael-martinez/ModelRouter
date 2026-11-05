#!/bin/bash
# Installe ou retire le routage Claude Code de ModelRouter dans un fichier de réglages Claude Code.
#
# Usage :
#   install.sh [--project DIR]        DIR/.claude/settings.local.json (défaut : dossier courant)
#   install.sh --global               ~/.claude/settings.json (tous les projets)
#   install.sh --uninstall [--project DIR | --global]
#
# Ne touche qu'aux entrées de route-codex.sh et de limits-statusline.sh. Une barre d'état
# appartenant à un autre outil n'est jamais remplacée. Le fichier est sauvegardé avant modification.
# Requiert jq.
set -euo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="$SELF_DIR/route-codex.sh"
STATUS="$SELF_DIR/limits-statusline.sh"

mode="install"
project="$PWD"
target=""
while [ $# -gt 0 ]; do
  case "$1" in
    --global) target="$HOME/.claude/settings.json" ;;
    --project)
      [ $# -ge 2 ] || { echo "--project attend un dossier" >&2; exit 2; }
      project="$2"; shift ;;
    --uninstall) mode="uninstall" ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "option inconnue : $1" >&2; exit 2 ;;
  esac
  shift
done
[ -n "$target" ] || target="$project/.claude/settings.local.json"

command -v jq >/dev/null || { echo "jq est requis (brew install jq)" >&2; exit 1; }
[ -x "$HOOK" ] && [ -x "$STATUS" ] || { echo "scripts non exécutables dans $SELF_DIR" >&2; exit 1; }

mkdir -p "$(dirname "$target")"
[ -f "$target" ] || echo '{}' > "$target"
jq -e 'type == "object"' "$target" >/dev/null 2>&1 || { echo "$target n'est pas un objet JSON valide" >&2; exit 1; }

# Sauvegarde datée, jamais écrasée (deux installations dans la même seconde reçoivent un suffixe)
base="$target.bak-$(date +%Y%m%d-%H%M%S)"
backup="$base"
n=1
while [ -e "$backup" ]; do backup="$base-$n"; n=$((n + 1)); done
cp "$target" "$backup"
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

# Comme un éditeur : le fichier remplacé garde le mode d'origine (mktemp crée du 0600)
replace_target() {
  local mode
  mode="$(stat -f %Lp "$target" 2>/dev/null || stat -c %a "$target")"
  chmod "$mode" "$tmp"
  mv "$tmp" "$target"
}

# Retire les entrées de nos deux scripts, quel que soit leur chemin (migration incluse)
strip_ours='
  if .hooks.UserPromptSubmit then
    .hooks.UserPromptSubmit = [ (.hooks.UserPromptSubmit)[]
      | .hooks = [ (.hooks // [])[] | select((.command // "") | test("route-codex\\.sh\"?$") | not) ]
      | select(.hooks | length > 0) ]
    | if (.hooks.UserPromptSubmit | length) == 0 then del(.hooks.UserPromptSubmit) else . end
  else . end
  | if .hooks == {} then del(.hooks) else . end
  | if ((.statusLine.command // "") | test("limits-statusline\\.sh\"?$")) then del(.statusLine) else . end
'

if [ "$mode" = "uninstall" ]; then
  jq "$strip_ours" "$target" > "$tmp"
  replace_target
  echo "ModelRouter retiré de $target (sauvegarde : $backup)"
  exit 0
fi

current_sl="$(jq -r '.statusLine.command // ""' "$target")"
keep_statusline=0
if [ -n "$current_sl" ] && ! printf '%s' "$current_sl" | grep -q 'limits-statusline\.sh"\{0,1\}$'; then
  keep_statusline=1
  echo "Attention : une barre d'état existe déjà ($current_sl). Elle n'est pas remplacée," >&2
  echo "donc la bascule sur la limite Claude ne recevra pas les quotas." >&2
fi

jq --arg hook "\"$HOOK\"" --arg status "\"$STATUS\"" --argjson keep "$keep_statusline" "
  $strip_ours
  | .hooks = (.hooks // {})
  | .hooks.UserPromptSubmit = ((.hooks.UserPromptSubmit // []) + [{\"hooks\": [{\"type\": \"command\", \"command\": \$hook, \"timeout\": 300}]}])
  | if \$keep == 1 then . else .statusLine = {\"type\": \"command\", \"command\": \$status} end
" "$target" > "$tmp"
replace_target
echo "ModelRouter installé dans $target (sauvegarde : $backup)"
