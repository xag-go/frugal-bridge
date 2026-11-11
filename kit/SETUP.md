# Frugal-Bridge — setup on any AI host

**Quick start:** `python3 kit/setup.py install /path/to/project [--hosts claude-code,gemini,hermes] [--hermes-home ~/.hermes]`
· `python3 kit/setup.py check /path` · `python3 kit/setup.py uninstall /path`. Idempotent, reversible, backups in
`<project>/.frugal-bridge/backup/`. Works alone or next to a knowledge base / "base folder" (any install order:
marked block in `AGENTS.md`, `.kits.json` registry, slots — see "Coexistence" below).

The kit = `AGENTS.md` (rules) + `ROUTING.md` (tiers → models) + `templates/` + `skills/`.
Put your files (USER.md, PROGRESS.md, PROJECT.md, DECISIONS.md, sources/) in one folder per project or one base
folder. Name your main agent in `USER.md`.

| Host | How |
|---|---|
| Codex, Cursor, Gemini CLI, Amp, other AGENTS.md readers | Copy `AGENTS.md` to the project root; they read it automatically. Copy `skills/` where the host loads skills, else they stay as docs the agent reads on demand. |
| Claude Code | `python3 kit/setup.py install <project>` (does all of this): `AGENTS.md` block; `CLAUDE.md` = one line `@AGENTS.md` (the `@` import loads the file; a prose line like "Read AGENTS.md" does not); skills to `.claude/skills/frugal-*`; hooks merged into `.claude/settings.json` key by key (your own hooks/keys untouched). See `adapters/claude-code/` when built. |
| Hermes | Copy `AGENTS.md` into the workspace/profile context; skills to the profile's `skills/`. Plugin: `adapters/hermes/` when built. |
| ChatGPT / Claude.ai / Gemini apps (Projects) | Paste `AGENTS.md` + `ROUTING.md` + your `USER.md` into the project instructions; upload PROJECT/DECISIONS as project files. No plugin: the rules are advice there — start a new chat yourself when the agent proposes it. |
| Any host with a configurable API base URL (Codex, Cursor, Aider, OpenCode, Continue…) | Run `adapters/proxy/frugal_proxy.py`, set the host's base URL to `http://127.0.0.1:8790/<provider>`. Enforces the rules without host hooks. |
| API / your own app | System prompt = `AGENTS.md` + `ROUTING.md` + `USER.md` (keep it unchanged during a session for the cache). Do the adapter jobs in code: count tokens, offer new session at 150k, filter tool outputs, skip empty heartbeats, route helpers by tier. |

Fill `ROUTING.md` with the models you have. Check an independent benchmark (e.g. artificialanalysis.ai) for
candidates, then test on your own tasks (AGENTS.md section 8).

If the target already has a base folder / knowledge base: follow the coexistence contract (marked block in `AGENTS.md`, `.kits.json`, slots) — see `docs/COEXISTENCE.md`. Never overwrite an existing `AGENTS.md`.

## Coexistence with a base folder (or any other kit)
- Shared Markdown files (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`): edited only inside `<!-- frugal-bridge:start vN -->`
  … `<!-- frugal-bridge:end -->`; text outside is never touched; uninstall restores it byte for byte.
- JSON settings (`.claude/settings.json`; no comments, so no blocks): merged key by key — setup adds only hook entries
  whose command is its own `.frugal-bridge/frugal_hook.py`, replaces them on re-run, removes only them on uninstall.
  Invalid JSON → setup stops and changes nothing there.
- `.kits.json`: each kit writes only its own entry. If a base folder is registered, Frugal creates **no** USER/PROGRESS/
  DECISIONS files and its adapters read the base's `slots` (e.g. now = `hot.md`, user = `wiki/me/README.md`).
- Size: `setup.py check` measures the whole `AGENTS.md` (all blocks): Codex reads only the first 32 KiB.
- Pointer files: `@AGENTS.md` for Claude Code and Gemini CLI (Gemini also accepts `context.fileName: ["AGENTS.md"]`
  in `.gemini/settings.json`).
