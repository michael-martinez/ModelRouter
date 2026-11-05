---
id: SPEC-jev-hook-routing
companions: []
sources: []
---

> **Canonical contract.** This SPEC is the complete contract for what to build. Source documents are for traceability only.

# Routage Jev depuis le hook Claude Code

## Why

Dans une session Claude Code avec le hook installé, une question fermée que `ask` envoie à Jev part quand même vers Claude. Claude consomme alors des tokens pour une réponse que Jev sait donner seul, et le choix de ModelRouter n'est pas respecté. Le hook ne transmet aujourd'hui que les choix Codex.

## Capabilities

- **CAP-1**
  - **intent:** Quand `ask` choisit Jev pour un message, le hook donne la réponse de Jev, et le message n'atteint pas Claude.
  - **success:** Dans une session avec le hook installé, « Pâtes ou riz ? » reçoit la réponse de Jev, et aucune réponse de Claude n'est produite.
- **CAP-2**
  - **intent:** La réponse de Jev s'affiche comme celle de Codex : même préfixe `ModelRouter:<modèle>: `, même sortie.
  - **success:** La réponse commence par `ModelRouter:jev-latest: ` suivi du texte de Jev.

## Constraints

- La garde anti-boucle `MR_ROUTING` reste en place.
- Si `ask` échoue, Claude répond à la place, comme pour Codex.
- Le hook ne force jamais Jev : il applique le choix de `ask`, sans modifier les règles de routage.

## Non-goals

- Modifier les règles de choix de `ask`.
- Changer la logique de bascule sur la limite Claude.
- Gérer autrement un échec de Jev que par le repli sur Claude.

## Success signal

Une question fermée posée depuis Claude Code reçoit la réponse de Jev, préfixée par `ModelRouter:jev-latest: `, sans qu'une réponse de Claude apparaisse.

## Decisions

- Un message de suivi après une réponse Jev ne reste pas sur Jev : les règles de conversation de `ask` s'appliquent, sans changement.
- La confiance Jev apparaît dans le texte de la réponse, par exemple « Pâtes (confiance 62 %) ». Aucun champ dédié n'est ajouté au préfixe.

## Open Questions

- Aucune à ce stade.
