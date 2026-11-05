#!/bin/bash
# UserPromptSubmit : Codex répond ici quand ModelRouter le choisit, ou quand Claude est à court de limite.
# Sinon le message suit le chemin normal de Claude Code.
# Installé par install.sh ; ask est trouvé à partir de l'emplacement de ce script.
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASK="${MODELROUTER_ASK:-$SELF_DIR/../../bin/ask}"
LIMITS="$HOME/.config/model-router/claude-limits.json"
LIMIT_PERCENT=95

# Garde anti-boucle : ask peut lancer un agent qui rouvrirait Claude Code et ce hook.
[ -n "$MR_ROUTING" ] && exit 0

prompt=$(jq -r '.prompt // empty')
[ -z "$prompt" ] && exit 0

# Préfixe « c: » : ce message va à Claude, même pendant une conversation Codex ou une limite atteinte
case "$prompt" in "c: "*) exit 0 ;; esac

# Préfixe « r: » : repart d'une conversation vide, puis traite le reste du message normalement
case "$prompt" in "r: "*)
  "$ASK" --reset </dev/null >/dev/null 2>&1
  prompt="${prompt#r: }"
  [ -z "$prompt" ] && exit 0
  ;;
esac

# Commandes slash : toujours Claude
case "$prompt" in /*) exit 0 ;; esac

# Pièces jointes (images, fichiers) : Codex ne les voit pas, toujours Claude
case "$prompt" in *"[Image #"*|*"[Pasted"*) exit 0 ;; esac

# Limite Claude atteinte : fenêtre 5 h ou semaine au-dessus du seuil et pas encore réinitialisée.
# Pas de contrôle de fraîcheur : la barre d'état n'écrit qu'après une réponse de Claude, donc le fichier
# peut être ancien alors que la limite est toujours atteinte. L'heure de réinitialisation suffit.
claude_exhausted() {
  [ -f "$LIMITS" ] || return 1
  jq -e --argjson now "$(date +%s)" --argjson t "$LIMIT_PERCENT" '
    ([ [.five_hour, .seven_day][] | select(. != null and .used_percentage >= $t and .resets_at > $now) ] | length) > 0
  ' "$LIMITS" >/dev/null 2>&1
}

agent=""
if claude_exhausted; then
  agent="codex"
  # Limite atteinte : on demande à ask quel modèle Codex utilisera (sans rien lancer)
  choice=$("$ASK" --why --use codex "$prompt" </dev/null 2>&1 | grep '^→' | head -1)
else
  # ModelRouter choisit en tenant compte de la conversation en cours (suite sur Codex pendant 30 min)
  choice=$("$ASK" --why "$prompt" </dev/null 2>&1 | grep '^→' | head -1)
  case "$choice" in
    *"→ codex/"*) agent="codex" ;;
    *"→ jev/"*) agent="jev" ;;   # question fermée : Jev répond seul, Claude n'est pas appelé
  esac
fi
[ -n "$agent" ] || exit 0

# Modèle exact, par exemple « codex/gpt-6-luna » ou « jev/jev-latest » (ligne « → modèle · … »)
model=$(printf '%s' "$choice" | sed -n 's/^→ \([^ ]*\).*/\1/p')
name="${model#*/}"
label="ModelRouter:${name:-$agent}: "

# Sans --new : la conversation par dossier garde le fil (30 min).
export MR_ROUTING=1
if [ "$agent" = "codex" ]; then
  # --write : Codex peut modifier les fichiers du dossier, comme Claude Code le ferait.
  answer=$("$ASK" --write --use codex "$prompt" </dev/null 2>/dev/null)
else
  answer=$("$ASK" --use jev "$prompt" </dev/null 2>/dev/null)
fi
status=$?

# Échec : Claude répond à la place, la question n'est pas perdue
if [ $status -ne 0 ] || [ -z "$answer" ]; then
  exit 0
fi

# Exit 2 : le message ne va pas à Claude (pas de tokens Claude), la réponse s'affiche ici
echo "${label}${answer}" >&2
exit 2
