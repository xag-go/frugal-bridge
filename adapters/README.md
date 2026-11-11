# Frugal-Bridge adapters

Adapters do the parts of the kit a prompt cannot guarantee. The rules themselves stay in `kit/AGENTS.md`.

**Start files = slots.** All three adapters (Hermes, Claude Code, proxy) read the "now" and "user" files from
`.kits.json` `slots` (searched in the project folder and up to 3 parents), else `PROGRESS.md` / `USER.md`; read order
now → user. So they work the same with or without a base folder.

## Hermes (`hermes/frugal-bridge/`)
Plugin with four hooks + one command:
| Piece | What it does |
|---|---|
| `pre_api_request` / `post_api_request` | Track each session's context size; log every main-model call to `$HERMES_HOME/frugal-bridge/usage.jsonl` |
| `pre_llm_call` | Past 150k tokens (100k on cheap models) → once, ask the agent to offer new session / compact / carry on at the end of its reply; at 300k say it plainly. First turn: if `base_dir` has USER.md / PROGRESS.md, read them first in one call |
| `transform_terminal_output` | Output over 12k chars → head 40 + tail 60 lines + error-looking lines; full text saved to a file, path given |
| `/frugal [days]` | Usage table per model (calls, output, cache read, ~$ at API prices) + alerts (long sessions, >300 calls) |

Install (one profile): copy the folder to `$HERMES_HOME/plugins/frugal-bridge/`, then `hermes plugins enable frugal-bridge`
and restart the gateway. Optional `$HERMES_HOME/frugal-bridge/config.json`:
`{"base_dir": "/path/to/folder/with/USER.md", "ctx_warn": 150000, "ctx_hard": 300000, "ctx_warn_cheap": 100000, "out_limit": 12000}`.
Uninstall: `hermes plugins disable frugal-bridge` and delete the folder.

Tests: `pytest -q adapters/hermes/test_plugin.py` (14 unit tests incl. `.kits.json` slots) + loaded through Hermes's own plugin manager
(hooks registered, dispatch checked, `/frugal` registered).

## Claude Code (`claude-code/frugal_hook.py`)
One script for two hook events: `SessionStart` (read USER.md + PROGRESS.md first if present) and `UserPromptSubmit`
(context watch from the transcript, same thresholds). Add to `.claude/settings.json` (project) or
`~/.claude/settings.json` (all projects):
```json
{"hooks": {
  "SessionStart":     [{"hooks": [{"type": "command", "command": "python3 /path/to/frugal_hook.py"}]}],
  "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "python3 /path/to/frugal_hook.py"}]}]
}}
```
Easiest: `python3 kit/setup.py install <project>` — writes `CLAUDE.md` = `@AGENTS.md` (an `@` import; a prose "Read
AGENTS.md" line does not load it), copies the skills (`frugal-*`) and merges these hooks into `.claude/settings.json`
key by key (other hooks and keys untouched; uninstall removes only ours).
Tested: fake transcripts (150k warns once, Haiku at 100k, missing transcript silent) + one real `claude -p` run
(context injected, the agent read USER.md and PROGRESS.md and answered from them).
Not covered in Claude Code: output filtering (no hook rewrites Bash output) → the `filter-output` skill.

## Proxy (`proxy/frugal_proxy.py`) — any host with a configurable API base URL
Stdlib-only HTTP proxy between the host and the provider. Point the host's base URL at
`http://127.0.0.1:8790/<route>` (routes: `anthropic`, `openai`, `chatgpt` (Codex with ChatGPT login), `openrouter`,
`gemini`, `xai`; more in config). Keys pass through untouched; the proxy stores none.
| Rule | How |
|---|---|
| Context watch | real usage from each response; past 150k (100k cheap) → one notice on the next user turn; 300k → plain |
| Loop guard | same tool call + same result twice, or two calls failing with the same error → one "stop and rethink" notice (free-text fields like `description` ignored) |
| Output filter | outputs of shell-like tools (`filter_tools`) > 12k chars cut (head + error lines + tail), full text saved under its hash (identical cut every request → cache stays valid); file reads never cut |
| Start files | `project_dir` set → first turn: read the now/user slot files (from `.kits.json`, else PROGRESS.md / USER.md) |
| CORE | `core_file` set → appended to the system prompt once (skipped if a `frugal-bridge:start` block is already there) |
| Usage | `usage.jsonl` + `GET /frugal/report?days=7` |
Notices go at the END of the request, never the start (prompt cache safe). Unknown formats = pure pass-through;
any internal error forwards the original body.
Config: `~/.config/frugal-bridge/proxy.json` (or `--config`); `dump_dir` = debug only. Limit: cannot start a new session itself.
Hosts: Claude Code `ANTHROPIC_BASE_URL=http://127.0.0.1:8790/anthropic`; Codex (ChatGPT login)
`-c model_provider=fb -c 'model_providers.fb={name="fb",base_url="http://127.0.0.1:8790/chatgpt",wire_api="responses",requires_openai_auth=true}'`;
OpenAI-compatible tools: base URL `http://127.0.0.1:8790/openai/v1` (or `/openrouter/v1`, `/gemini/v1beta/openai`).
Tests: `uvx --with pytest pytest -q adapters/proxy/test_proxy.py` (18) + real Claude Code run (RESULTS §2.22).

## Other hosts
Codex / Cursor / Gemini CLI read `AGENTS.md` directly; chat apps get the rules as project instructions (no
enforcement). See `kit/SETUP.md`.
