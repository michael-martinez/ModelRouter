---
title: "Product Brief: bmad-modelrouter"
status: final
created: 2026-11-05
updated: 2026-11-05
---

# Product Brief: ModelRouter

## Résumé

ModelRouter est un outil en ligne de commande, `ask`, qui envoie chaque question à l'agent IA le plus adapté parmi ceux déjà installés sur la machine : Claude, Codex, Gemini, Ollama. Une étape de classification (Jev) évalue d'abord la catégorie et la complexité de la question, puis choisit le modèle le moins cher capable de la traiter.

Dans Claude Code, un hook complète ce routage : lorsque la consommation de Claude (fenêtre de 5 heures ou semaine) atteint 95 % de la limite de l'abonnement, les messages suivants partent vers Codex. L'utilisateur n'a pas à changer ses habitudes.

Le projet est une réalisation personnelle, publiée sur GitHub sous licence MIT. Son premier objectif est de montrer, dans un portfolio public, une approche concrète de l'usage multi-IA. `[ASSUMPTION]` Il n'a pas vocation à devenir un produit commercial.

## Le problème

Un utilisateur qui paie plusieurs abonnements IA (Claude Pro, ChatGPT/Codex, etc.) doit décider à la main quel outil utiliser pour chaque question. Il peut faire un mauvais choix : un modèle coûteux pour une question simple, ou un modèle bloqué au pire moment parce que la limite de son abonnement est atteinte.

Les limites d'usage sont invisibles jusqu'au moment où elles tombent. Dans Claude Code, une session peut s'interrompre en pleine tâche, sans alternative immédiate.

## La solution

- **Choix automatique** : pour chaque question, ModelRouter classe la demande puis choisit le modèle le moins cher capable de la traiter, parmi ceux installés.
- **Continuité** : une conversation par dossier, valable 30 minutes. Un agent sans session native reçoit les questions précédentes et la dernière réponse, pour ne pas repartir de zéro.
- **Bascule dans Claude Code** : le hook envoie les messages vers Codex quand la limite approche (voir Résumé). Les préfixes `c: ` et `r: ` gardent la main à l'utilisateur.

Le routage repose sur des agents que l'utilisateur utilise déjà. ModelRouter ne fait pas d'appels API avec des clés propres.

## Ce qui le distingue

- **Il s'appuie sur les CLI existants** (`claude`, `codex`, `gemini`, `ollama`), pas sur une passerelle à payer.
- **Il garde une conversation entre agents** : une question de suivi sur Codex voit les échanges précédents avec Claude.
- **Il est petit et lisible** : un seul dépôt, des données de configuration simples (`data/catalog.json`).

Les outils concurrents sont plus matures ou plus complets (OpenCode, claude-code-router, OpenRouter, LiteLLM) : le README les compare.

## Qui l'utilise

- **Principal** : Michael, qui utilise déjà Claude Code et Codex et veut éviter les interruptions liées aux quotas.
- **Secondaire** : des développeurs qui ont plusieurs abonnements IA et qui lisent le dépôt pour voir une approche possible. `[ASSUMPTION]` Ce public reste marginal.

## Critères de succès

- **Usage personnel** : Michael n'est plus bloqué par une limite de quota dans Claude Code pendant une session de travail.
- **Visibilité** : le dépôt est lisible en quelques minutes, et la documentation rend compte du fonctionnement sans ambiguïté.
- `[ASSUMPTION]` **Public** : quelques étoiles ou retours sur GitHub. Ce critère n'est pas un objectif, il sert à savoir si le dépôt est vu.

## Périmètre

**Dans le périmètre actuel**
- Classification par Jev, choix du modèle, conversation, repli sur l'agent suivant.
- Bascule Claude vers Codex à 95 % de la fenêtre 5 h ou semaine, dans Claude Code.
- Commandes `scan`, `--why`, `--use`, `--write`, `--reset`, `--new`.

**Hors périmètre**
- Serveur proxy compatible OpenAI, apprentissage à partir des choix forcés par `--use`, interface graphique.
- Lecture des quotas depuis les fichiers de session locaux : abandonnée au profit de la status line.

**Hypothèse de travail** `[ASSUMPTION]`
- Le hook Claude Code est livré dans `integrations/claude-code/`, en installation optionnelle par projet (`--project`) ou globale (`--global`), avec désinstallation. Il ne route que vers Codex ; Jev reste accessible via `ask`.

## Ouvert

- Le projet est considéré comme terminé, sans évolution prévue à ce stade. Aucune version n'est nommée.
- Dépendance à Jev, un service externe payant. Sans clé, le routage repose sur le profil par défaut.
