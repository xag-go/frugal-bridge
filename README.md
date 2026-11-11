# Frugal-Bridge

> **If you are an AI agent asked to set this up: read [`INSTALL.md`](INSTALL.md) and follow it.**
> Humans: give your agent this repo link and say "set up Frugal-Bridge for me".

**Spend fewer tokens on AI agents without losing quality.** A small, portable set of working rules plus adapters that
enforce them — for any agent host (Claude Code, Codex, Gemini CLI, Cursor, Hermes, your own app) and any provider.

Every rule here was A/B tested (3+ runs per cell, real checks first — hidden tests, exact answers — then a blind
judge, and a human rater for language). Rules that saved tokens but lowered quality were dropped.
Numbers: [`docs/RESULTS.md`](docs/RESULTS.md). Reasoning, rejected ideas and open items: [`docs/DESIGN.md`](docs/DESIGN.md).

## What it does
| Lever | Measured effect (our tests) |
|---|---|
| New session per task + a short handoff (save pasted material to files first) | −51% to −90% on long work, decisions and reasons kept |
| Route work by kind: checkable work to the cheap tier (with escalation on a failed check), judgment work straight to the right tier | cheap tier 10–50× cheaper on checkable tasks at the same quality |
| Medium effort by default; no xhigh/max | xhigh/max 3–17× cost, no gain; max sometimes returned nothing |
| Filter big tool outputs before they enter the context | −63% to −75%, same result |
| Split memory files (USER / PROJECT / DECISIONS / PROGRESS) instead of one growing handoff | −45%, same quality |
| One reviewer picked by the stakes instead of several | −66% to −96%, fewer false alarms |
| Large pasted inputs as files handed to a cheap helper | −57% in the main chat |
| Load only the tools a job needs (deferred loading) | +36% avoided on a cheap model |
| Heartbeats check for changes before calling a model | $0 per empty run |

Also found: on one subscription plan, output weighed ~2.2× more than cached input per API dollar — so effort and
verbose output are the main levers there.

## Quick start
```bash
git clone https://github.com/xag-go/frugal-bridge && cd frugal-bridge
python3 kit/setup.py install /path/to/your/project            # AGENTS.md block, CLAUDE.md/GEMINI.md pointers, skills, Claude Code hooks
python3 kit/setup.py check /path/to/your/project
python3 kit/setup.py uninstall /path/to/your/project          # restores your files byte for byte
```
Before installing, edit `kit/ROUTING.md` with the models you use (re-run `install` after any change). Then name your
main agent in the project's `USER.md`.

| Host | How the rules are enforced |
|---|---|
| Claude Code | `AGENTS.md` via `@AGENTS.md` + hooks (context watch, start files) — [`adapters/claude-code`](adapters/claude-code) |
| Hermes Agent | plugin (context watch, start files, output filter, `/frugal` usage report) — [`adapters/hermes`](adapters/hermes) |
| Any host with a configurable API base URL (Codex, Cursor, Aider, OpenCode…) | local proxy — [`adapters/proxy`](adapters/proxy) |
| Codex / Gemini CLI / Cursor without the proxy | they read `AGENTS.md` directly (rules followed, not enforced) |
| Chat apps (ChatGPT, Claude.ai, Gemini) | paste `kit/AGENTS.md` into project instructions (advice only) |

Details per host: [`kit/SETUP.md`](kit/SETUP.md). Works alone or next to a knowledge-base folder, in any install
order: [`docs/COEXISTENCE.md`](docs/COEXISTENCE.md).

## What's inside
- `kit/AGENTS.md` — the rules (~7 KB). `kit/ROUTING.md` — cheap / mid / top tiers → your models.
- `kit/templates/` — USER, PROJECT, PROGRESS, DECISIONS, MAP, ROLE, helper BRIEF.
- `kit/skills/frugal-*` — handoff, new-session, delegate, save-sources, new-agent, filter-output.
- `kit/setup.py` — install / check / uninstall (idempotent, reversible, backups).
- `adapters/` — Hermes plugin, Claude Code hook, provider proxy.

## Tests
```bash
python3 -m pip install pytest
python3 -m pytest -q kit adapters
```

## Limits (honest)
- Tested mostly on Anthropic models (Claude Haiku / Sonnet / Opus 5.5); OpenAI and Google tiers in `ROUTING.md` are
  candidates, not yet measured.
- Chat apps cannot be enforced (no hooks, no base URL).
- The test harness and raw runs are not published (they contain private material); `docs/RESULTS.md` has every number.

License: MIT.
