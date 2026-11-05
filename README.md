# ModelRouter

Une CLI qui choisit, pour chaque question, le modèle d'IA installé le plus adapté, puis le lance.

```bash
ask "refactor ce module"           # choisit l'agent, affiche son choix, lance la réponse
ask "Pâtes ou riz ?"               # question fermée : répondue par Jev, sans lancer d'agent
ask --why "question"               # montre le choix et la commande, sans rien lancer
ask --use codex "question"         # force un agent
```

Le routeur classe d'abord la question (type de tâche et complexité de 0 à 4) grâce à Jev, un service de classification. Il retient ensuite le modèle le moins cher capable de la traiter parmi ceux qui sont installés sur la machine : Claude, Codex, Gemini, Ollama, ou Jev lui-même pour les questions fermées.

## Installation

Prérequis : Python 3.9 et les CLI des agents que tu veux utiliser (`claude`, `codex`, `gemini`, `ollama`).

```bash
git clone https://github.com/michael-martinez/ModelRouter.git
cd ModelRouter
ln -s "$PWD/bin/ask" ~/.local/bin/ask    # ou un autre dossier du PATH
export JEV_API_KEY=...                   # facultatif : active la classification et les questions fermées
ask scan                                 # détecte les agents et les modèles installés
```

`ask scan` écrit l'inventaire dans `~/.config/model-router/inventory.json`. Relance-le après chaque installation ou modification du catalogue.

## Fonctionnement

- **Choix** : parmi les modèles capables (niveau suffisant pour la catégorie et la complexité), le moins cher gagne. Si aucun n'est capable, le plus compétent installé est utilisé.
- **Conversation** : un fil par dossier, valable 30 minutes. Un agent qui n'a pas de session native reçoit les questions précédentes et la dernière réponse.
- **Codex** : lancé en lecture seule. `--write` l'autorise à modifier les fichiers du dossier.
- **Repli** : si un agent échoue sans rien produire, le modèle suivant prend la main.

## Catalogue

`data/catalog.json` décrit les agents, leurs commandes et les niveaux de chaque modèle. C'est de la donnée : tu peux ajuster les coûts et les niveaux. Pour Codex, les modèles absents du compte connecté sont écartés au scan.

## Tests

```bash
python3 -m venv .venv && .venv/bin/pip install pytest
.venv/bin/python -m pytest
```

Les tests utilisent de faux objets uniquement aux frontières (HTTP de Jev, PATH, lancement des agents).

## Limites connues

- Le routage dépend de la classification de Jev : sans clé, le profil par défaut est utilisé.
- Les agents sont appelés via leur CLI. Leurs options (sandbox, modèles disponibles) peuvent changer d'une version à l'autre.
- Les questions fermées sont détectées par leur forme : une question courte du type « X ou Y ? » part vers Jev.
