#!/bin/bash
# Barre d'état Claude Code : affiche les limites et les écrit pour le hook route-codex.sh.
# Requiert jq. Installé par install.sh.
LIMITS_DIR="$HOME/.config/model-router"
LIMITS="$LIMITS_DIR/claude-limits.json"

input=$(cat)
mkdir -p "$LIMITS_DIR"

# Écriture seulement si les limites sont présentes (abonnés claude.ai, après la première réponse)
if printf '%s' "$input" | jq -e '.rate_limits' >/dev/null 2>&1; then
  printf '%s' "$input" | jq --argjson now "$(date +%s)" \
    '{updated: $now, five_hour: .rate_limits.five_hour, seven_day: .rate_limits.seven_day}' \
    > "$LIMITS.tmp" && mv "$LIMITS.tmp" "$LIMITS"
fi

# Affichage
printf '%s' "$input" | jq -r '
  def pct(w): if w == null then "–" else "\(w.used_percentage | floor)%" end;
  "limites  5h \(pct(.rate_limits.five_hour))  ·  semaine \(pct(.rate_limits.seven_day))"
' 2>/dev/null || echo "limites indisponibles"
