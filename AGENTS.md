# ModelRouter : choisir le modèle installé le plus adapté

CLI `ask` : Jev (TypeSafe systemone) classe la question en moins d'une seconde (type de tâche + complexité 0-4), puis l'agent installé le plus adapté est lancé.

## Usage
```bash
bin/ask scan                          # détecte agents + modèles → ~/.config/model-router/inventory.json
export JEV_API_KEY=...                # active Jev (classification et questions fermées)
bin/ask "refactor ce module"          # choisit, affiche le choix sur stderr, lance l'agent (sortie en direct)
bin/ask "et en Kotlin ?"              # relance : garde le fil de la conversation
bin/ask --new "autre sujet"           # repart de zéro
bin/ask --reset                       # vide la conversation du dossier courant, sans rien lancer
bin/ask "Pâtes ou riz ?"              # question fermée courte : Jev répond seul
cat avis.txt | bin/ask "classe en bug/ux/paiement"   # Jev classe chaque ligne + répartition
bin/ask --why "question"              # affiche le choix + la commande, sans lancer
bin/ask --use claude "question"       # force un agent (ou claude/opus pour un modèle), sans Jev
bin/ask --write --use codex "…"       # Codex peut modifier les fichiers du dossier (sinon lecture seule)
```
Alias conseillé : `ln -s "$PWD/bin/ask" ~/.local/bin/ask`.

## Règle de choix (domain/inventory.py, usecases/route_question.py)
0. Question fermée courte (≤ 120 caractères, forme reconnue) et Jev disponible : Jev, quelle que soit la catégorie
1. Modèles capables : `skills[catégorie] >= complexité`
2. Parmi eux : `cost_tier` minimal, puis meilleur niveau, puis ordre du catalogue
3. Aucun capable : le plus compétent installé
4. Jev indisponible (pas de clé, timeout 2 s, erreur) : `default_profile` du catalogue, jamais bloquant

Le catalogue `data/catalog.json` est de la donnée : niveaux et coûts à ajuster librement. Après une modification, relancer `ask scan` : la commande de chaque agent est copiée dans l'inventaire.

## Catalogue
- `filter_by_account` (Codex) : au scan, seuls les modèles présents dans le cache de compte de Codex (`~/.codex/models_cache.json`) sont gardés ; les autres sont signalés `ignoré : absent de ton compte`. Sans cache lisible, rien n'est filtré.
- Codex tourne en `-s {sandbox}` : `read-only` par défaut, `workspace-write` avec `--write`. `--skip-git-repo-check` permet de le lancer hors dépôt git.
- Claude tourne avec `--allowedTools=WebSearch,WebFetch,Read,Grep,Glob` (lecture seule).

## Jev répondeur (domain/closed_question.py, infra/jev_answerer.py)
- Catégorie `classification` + agent intégré `jev` (coût 0, actif si JEV_API_KEY au scan)
- Formes reconnues : oui/non (inversion « est-il », « est-ce que »…), options « A, B ou C », « A/B/C », « X ou Y » en fin de phrase. Le texte entre guillemets « » est ignoré pour l'extraction
- Contenu pipé : une ligne = un élément classé, puis répartition
- Forme non reconnue ou erreur Jev → repli sur le modèle suivant ; Jev n'est jamais un repli générique

## Repli
- Un agent qui échoue sans rien produire (auth expirée, binaire cassé, modèle refusé) passe la main au modèle suivant ; pas de repli s'il a commencé à répondre ou s'il a été interrompu

## Conversation (domain/conversation.py)
- Une conversation par dossier courant (`~/.config/model-router/conversations/<hash>.json`), expire après 30 min d'inactivité ; `--new` repart de zéro, `--reset` vide sans lancer
- Agent collant : on reste sur l'agent du dernier tour, seul le modèle change. Changement d'agent seulement si l'agent courant n'a aucun modèle au niveau requis et qu'un autre l'a, ou s'il échoue
- Session native (Claude) : 1er tour `--session-id <uuid>`, ensuite `--resume <uuid> --model <m>`. Jamais `--continue` (reprendrait la session interactive de l'utilisateur)
- Injection de contexte pour un agent sans session par id (Codex, Gemini…) : la liste des questions des 5 derniers échanges et la **seule dernière réponse**, marquée « à ne reprendre que si la question la concerne ». Les anciennes réponses ne sont pas réinjectées, pour qu'une mauvaise réponse ne soit pas recopiée
- `--resume` qui échoue sans rien produire → nouvelle session + historique injecté
- Jev classe chaque question avec la précédente ; réponse en échec ou `--why` : rien n'est mémorisé
- Niveau 0 dans une catégorie = ne sait pas faire (jamais choisi, même pour une complexité 0)

## Intégration Claude Code (hors du dépôt)
Ces fichiers vivent dans `~/.claude/hooks/` et dans `one-week-apps/.claude/settings.local.json` :
- `route-codex.sh` (UserPromptSubmit) : si ModelRouter choisit Codex, ou si Claude a atteint sa limite, Codex répond dans le terminal et le message ne va pas à Claude. Tout le reste suit le chemin normal de Claude Code.
  - Exemptions : `c: ` (force Claude), commandes slash, pièces jointes (`[Image #`, `[Pasted`)
  - `r: ` vide la conversation puis traite le reste du message
  - Les modifications de fichiers ne sont pas exemptées : Codex, s'il est choisi, écrit dans le dossier. Claude ne voit pas ces changements tant qu'on ne les lui décrit pas.
- `limits-statusline.sh` (statusLine) : affiche les limites 5 h et semaine, et les écrit dans `~/.config/model-router/claude-limits.json`. Le hook considère Claude à court dès qu'une fenêtre atteint 95 % avant sa réinitialisation.
  - Ne s'exécute que dans les sessions de ce projet. Les limites ne sont fournies que pour les abonnements claude.ai, après la première réponse.

## Dev
- Python 3.9 système, stdlib uniquement au runtime ; pytest dans `.venv`
- Tests : `.venv/bin/python -m pytest` (via `ScanAgents`, `RouteQuestion` et `cli.main`, avec des faux uniquement aux frontières : HTTP Jev, PATH, launcher)
- Le hook et la barre d'état ne sont pas couverts par pytest : vérifiés à la main avec des entrées JSON

## Hors scope
- Proxy HTTP compatible OpenAI
- Apprendre des choix forcés via `--use`
- Lancer via clé API seule, sans CLI installé (aujourd'hui simple indication au scan)
- Quotas par lecture des sessions locales : abandonné au profit des pourcentages fournis par la barre d'état
