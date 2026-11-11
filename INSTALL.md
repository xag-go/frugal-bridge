# INSTALL.md — instructions for an AI agent

You are an AI agent and the user asked you to **set up Frugal-Bridge** for them. Follow these steps in order. Talk to
the user in their language. Ask questions only in step 1, all in one message. Do not ask for API keys; never write
keys into any file.

## 0. What you are installing
Frugal-Bridge = working rules that cut token use without lowering quality (`kit/AGENTS.md`) + an adapter that
enforces them on this host. `kit/setup.py` does the file work; it is safe to re-run and fully reversible
(`uninstall`), it edits only inside its own marked block and keeps backups in `<project>/.frugal-bridge/backup/`.

## 1. Ask the user (one message)
1. **Which folder** should use it? (Default: the current project folder.)
2. **A name for the main agent** (any name; e.g. "Sara").
3. **Language and answer style** (e.g. "English, short", "Darija in Latin letters, short").
4. **Which models** they can use, if you can't tell yourself (e.g. Claude Haiku/Sonnet/Opus, GPT, Gemini).
Use sensible defaults for anything they skip.

## 2. If you have no shell
If you cannot run commands (a chat app), tell the user to paste `kit/AGENTS.md` and `kit/ROUTING.md` into the
project instructions — that is the whole setup there — and stop.

## 3. Set the model tiers
Open `kit/ROUTING.md` (in this repository) and make the `cheap / mid / top` rows match the models the user has.
If only one provider is available, fill only that column. Keep effort defaults (medium; high only for public writing).

## 4. Install
```bash
python3 kit/setup.py install "<folder>"
```
Setup finds the agent tools on this machine by itself and installs the adapter in the strongest way each tool allows
(hooks, plugin, or proxy suggestion). The report must start with `OK`; if it says `PROBLEMS`, show the lines to the
user and stop. It never overwrites the user's text, and if a settings file is not valid JSON it stops without
changing it — tell the user, don't "fix" their file.

The report ends with "Enforcement on this machine". Two lines may need the user's yes:
- **plugin copied … enable it**: enabling restarts that tool's gateway (running chats pause a few seconds). Ask, then
  run the enable command the tool documents (e.g. `hermes plugins enable frugal-bridge`, then restart its gateway).
- **proxy available for …**: see step 6.

## 5. Fill the user files
- If `<folder>/.kits.json` lists `base-folder`, a knowledge base owns the user files: **do not create or edit USER/
  PROGRESS files**; add the agent name and style only if the base's own rules say where.
- Otherwise open `<folder>/USER.md` and fill: main agent name, language and script, answer style. Leave the other
  lines for later. Don't touch `PROGRESS.md` / `DECISIONS.md` beyond their headings.

## 6. Optional: proxy (hosts with a configurable API base URL)
Only if setup listed tools for the proxy, the user wants the rules enforced there, and agrees to run a small local server:
```bash
python3 adapter/proxy/frugal_proxy.py --port 8790      # keep it running (e.g. a user service)
```
Then point the host at it — examples in `adapter/README.md`. Keys pass through untouched; the proxy
stores none. Skip this step if unsure.

## 7. Check and report
```bash
python3 kit/setup.py check "<folder>"
```
Tell the user, briefly: what was installed and where, which rules are **enforced** on this machine (from the
"Enforcement" lines) and that all other rules are **followed** by the agent, the main agent's name, and how to undo:
`python3 kit/setup.py uninstall "<folder>"` (plus the tool's disable command if a plugin was enabled).
A new session is needed for the rules to load.
