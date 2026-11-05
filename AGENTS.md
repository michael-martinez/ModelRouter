# ModelRouter: choose the most suitable installed model

`ask` CLI: Jev (TypeSafe systemone) classifies the question in under a second (task category + complexity 0-4), then the most suitable installed agent is launched.

## Usage
```bash
bin/ask scan                          # detects agents + models → ~/.config/model-router/inventory.json
export JEV_API_KEY=...                # enables Jev (classification and closed questions)
bin/ask "refactor this module"        # chooses, prints the choice on stderr, runs the agent (live output)
bin/ask "and in Kotlin?"              # follow-up: keeps the conversation thread
bin/ask --new "other topic"           # starts from scratch
bin/ask --reset                       # empties the current directory's conversation, runs nothing
bin/ask "Pâtes ou riz ?"              # short closed question: Jev answers alone
cat notes.txt | bin/ask "classify as bug/ux/payment"   # Jev classifies each line + distribution
bin/ask --why "question"              # shows the choice + the command, runs nothing
bin/ask --use claude "question"       # forces an agent (or claude/opus for a model), without Jev
bin/ask --write --use codex "…"       # lets Codex modify files in the directory (read-only otherwise)
```
Suggested alias: `ln -s "$PWD/bin/ask" ~/.local/bin/ask`.

## Choice rules (domain/inventory.py, usecases/route_question.py)
0. Short closed question (≤ 120 characters, recognised form) and Jev available: Jev, whatever the category
1. Capable models: `skills[category] >= complexity`
2. Among them: lowest `cost_tier`, then best level, then catalog order
3. No capable model: the most competent installed one
4. Jev unavailable (no key, 2 s timeout, error): `default_profile` from the catalog, never blocking

The catalog `data/catalog.json` is data: levels and costs can be adjusted freely. After a change, run `ask scan` again: each agent's command is copied into the inventory.

## Catalog
- `filter_by_account` (Codex): at scan time, only models present in Codex's account cache (`~/.codex/models_cache.json`) are kept; the others are reported as `ignoré : absent de ton compte`. Without a readable cache, nothing is filtered.
- Codex runs with `-s {sandbox}`: `read-only` by default, `workspace-write` with `--write`. `--skip-git-repo-check` allows running outside a git repository.
- Claude runs with `--allowedTools=WebSearch,WebFetch,Read,Grep,Glob` (read-only).

## Jev answerer (domain/closed_question.py, infra/jev_answerer.py)
- Category `classification` + built-in agent `jev` (cost 0, active if JEV_API_KEY is set at scan time)
- Recognised forms: yes/no (inversion such as "est-il", "est-ce que"…), options "A, B ou C", "A/B/C", "X ou Y" at the end of the sentence. Text between « » quotes is ignored for extraction
- Piped content: one line = one item classified, then distribution
- Unrecognised form or Jev error → fallback to the next model; Jev is never a generic fallback

## Fallback
- An agent that fails without producing anything (expired auth, broken binary, refused model) hands over to the next model. No fallback once it has started answering or was interrupted

## Conversation (domain/conversation.py)
- One conversation per current directory (`~/.config/model-router/conversations/<hash>.json`), expires after 30 min of inactivity. `--new` starts over, `--reset` empties without running anything
- Sticky agent: stays on the agent of the last turn; only the model changes. The agent changes only if the current one has no model at the required level and another one does, or if it fails
- Native session (Claude): first turn `--session-id <uuid>`, then `--resume <uuid> --model <m>`. Never `--continue` (it would resume the user's interactive session)
- Context injection for agents without a session id (Codex, Gemini…): the questions of the last 5 exchanges and **only the last answer**, marked "to reuse only if the new question concerns it". Earlier answers are not re-injected, so a bad answer cannot be copied over and over
- `--resume` that produces nothing → new session + injected history
- Jev classifies each question together with the previous one; a failed answer or `--why` stores nothing
- Level 0 in a category = cannot do it (never chosen, even for complexity 0)

## Claude Code integration (`integrations/claude-code/`, optional)
Installed by `integrations/claude-code/install.sh` (`--project DIR` or `--global`, `--uninstall` to remove). The scripts stay in the repository and are referenced from the settings file:
- `route-codex.sh` (UserPromptSubmit): if ModelRouter chooses Codex, or if Claude has hit its limit, Codex answers in the terminal and the message never reaches Claude. Everything else follows Claude Code's normal path.
  - Exemptions: `c: ` (forces Claude), slash commands, attachments (`[Image #`, `[Pasted`)
  - `r: ` empties the conversation, then processes the rest of the message
  - File modifications are not exempted: if Codex is chosen, it writes to the directory. Claude does not see those changes unless they are described to it.
- `limits-statusline.sh` (statusLine): shows the 5 h and weekly limits, and writes them to `~/.config/model-router/claude-limits.json`. The hook considers Claude exhausted as soon as a window reaches 95% before its reset.
  - Runs only in sessions where the installer added it. Limits are only provided for claude.ai subscriptions, after the first response.
  - The hook only routes to Codex: a choice of Jev is not handed over, so Jev questions from Claude Code still reach Claude.

## Dev
- System Python 3.9, stdlib only at runtime; pytest in `.venv`
- Tests: `.venv/bin/python -m pytest` (through `ScanAgents`, `RouteQuestion` and `cli.main`, with fakes only at the boundaries: Jev HTTP, PATH, launcher)
- The hook and the status line are not covered by pytest: checked by hand with JSON inputs

## Out of scope
- OpenAI-compatible HTTP proxy
- Learning from forced choices via `--use`
- Running with an API key alone, without the CLI installed (today only a hint at scan time)
- Quota reading from local session files: dropped in favour of the percentages provided by the status line
