#!/usr/bin/env python3
"""Frugal-Bridge setup: install / uninstall / check the kit in a project folder, following the coexistence contract
(docs/COEXISTENCE.md): marked blocks only, `.kits.json` registry, slots owned by a base folder when
present, key-level JSON merge for host settings, idempotent, reversible, backups of every touched file.

  python3 setup.py install   <dir> [--hosts claude-code,gemini,hermes] [--hermes-home PATH]
  python3 setup.py uninstall <dir>
  python3 setup.py check     <dir>

Hermes: copies the plugin into <hermes-home>/plugins/frugal-bridge and writes its config; enabling it
(`hermes plugins enable frugal-bridge` + gateway restart) is left to the owner.
"""
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys

KIT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(KIT)
VERSION = "6"
START, END = "<!-- frugal-bridge:start v{v} -->", "<!-- frugal-bridge:end -->"
START_RE = re.compile(r"<!-- frugal-bridge:start v[^>]*-->")
BASE_END = "<!-- base-folder:end -->"
POINTER = "@AGENTS.md"
CODEX_LIMIT = 32 * 1024     # Codex default project_doc_max_bytes
SOFT_LIMIT = 24 * 1024
HOOK_MARK = ".frugal-bridge/frugal_hook.py"
DEFAULT_SLOTS = {"user": "USER.md", "now": "PROGRESS.md", "decisions": "DECISIONS.md", "map": "MAP.md", "sources": "sources/"}
SLOT_TEMPLATES = {"user": "USER.md", "now": "PROGRESS.md", "decisions": "DECISIONS.md"}


def sha(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()


def read(p):
    return open(p, encoding="utf-8").read() if os.path.exists(p) else None


def write(p, text):
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


class Setup:
    def __init__(self, d):
        self.d = os.path.abspath(d)
        self.backup_dir = None
        self.log = []
        self._modes = {}

    # ---------------------------------------------------------------- helpers
    def p(self, rel):
        return os.path.join(self.d, rel)

    def backup(self, rel):
        src = self.p(rel)
        if not os.path.exists(src):
            return
        if not self.backup_dir:
            self.backup_dir = self.p(f".frugal-bridge/backup/{dt.datetime.now():%Y%m%d-%H%M%S-%f}")
        dst = os.path.join(self.backup_dir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)

    def kits(self):
        t = read(self.p(".kits.json"))
        try:
            return json.loads(t) if t else {}
        except json.JSONDecodeError:
            raise SystemExit(".kits.json is not valid JSON; fix it by hand first (nothing changed).")

    def save_kits(self, k):
        new = json.dumps(k, indent=2, ensure_ascii=False) + "\n"
        if read(self.p(".kits.json")) != new:
            self.backup(".kits.json"); write(self.p(".kits.json"), new)

    def change(self, rel, new):
        """Write rel only if content differs (keeps re-runs byte-identical)."""
        if read(self.p(rel)) == new:
            return False
        self.backup(rel); write(self.p(rel), new); self.log.append(f"wrote {rel}")
        return True

    @staticmethod
    def find_block(text):
        if not text:
            return None
        m = START_RE.search(text)
        if not m:
            return None
        e = text.find(END, m.end())
        return (m.start(), e + len(END)) if e >= 0 else None

    def strip_block(self, text, mode=None):
        """Remove our block and exactly the separators put_block added (mode recorded at install)."""
        r = self.find_block(text)
        if not r:
            return text, False
        a, b = r
        mode = mode or "append"
        if mode == "new":
            if text[b:b + 1] == "\n":
                b += 1
        elif mode == "after-base":
            if text[a - 2:a] == "\n\n":
                a -= 2
        else:  # append / append-noeol
            if text[b:b + 1] == "\n":
                b += 1
            if text[a - 1:a] == "\n":
                a -= 1
            if mode == "append-noeol" and text[a - 1:a] == "\n":
                a -= 1
        return text[:a] + text[b:], True

    def core(self, body):
        return f"{START.format(v=VERSION)}\n{body.rstrip()}\n{END}"

    def put_block(self, rel, body, after_base=True):
        """Insert or replace our block; returns the placement mode (stored in .kits.json for exact removal)."""
        old = read(self.p(rel))
        core = self.core(body)
        r = self.find_block(old)
        modes = self._modes
        if r:  # replace in place, keep the recorded mode
            new = old[:r[0]] + core + old[r[1]:]
            self.change(rel, new)
            return modes.get(rel, "append")
        if not old:
            mode, new = "new", core + "\n"
        elif after_base and BASE_END in old:
            i = old.index(BASE_END) + len(BASE_END)
            mode, new = "after-base", old[:i] + "\n\n" + core + old[i:]
        elif old.endswith("\n"):
            mode, new = "append", old + "\n" + core + "\n"
        else:
            mode, new = "append-noeol", old + "\n\n" + core + "\n"
        self.change(rel, new)
        return mode

    # ---------------------------------------------------------------- install
    def install(self, hosts=("claude-code", "gemini"), hermes_home=None):
        os.makedirs(self.d, exist_ok=True)
        k = self.kits()
        kits = k.setdefault("kits", {})
        prev = kits.get("frugal-bridge", {})
        created = set(prev.get("created", []))
        hashes = dict(prev.get("template_hashes", {}))
        base = "base-folder" in kits
        self._modes = dict(prev.get("placement", {}))

        # 1. AGENTS.md block (after the base block when present)
        existed = os.path.exists(self.p("AGENTS.md"))
        self._modes["AGENTS.md"] = self.put_block(
            "AGENTS.md", open(os.path.join(KIT, "AGENTS.md")).read() + "\n\n" + open(os.path.join(KIT, "ROUTING.md")).read())
        if not existed:
            created.add("AGENTS.md")

        # 2. pointer files: one line '@AGENTS.md' (Claude Code / Gemini CLI import it; plain prose does not load it)
        for rel, host in (("CLAUDE.md", "claude-code"), ("GEMINI.md", "gemini")):
            if host not in hosts:
                continue
            t = read(self.p(rel))
            if t is None:
                self.change(rel, POINTER + "\n"); created.add(rel)
            elif self.find_block(t) or not any(l.strip() == POINTER for l in t.splitlines()):
                self._modes[rel] = self.put_block(rel, POINTER, after_base=False)

        # 3. slots: base owns them when present; else Frugal's own files (created once, from templates)
        slots = k.setdefault("slots", {})
        if not base:
            for name, default in DEFAULT_SLOTS.items():
                slots.setdefault(name, default)
            for name, tpl in SLOT_TEMPLATES.items():
                rel = slots[name]
                if not os.path.exists(self.p(rel)):
                    body = open(os.path.join(KIT, "templates", tpl)).read()
                    write(self.p(rel), body); created.add(rel); hashes[rel] = sha(body); self.log.append(f"created {rel}")
            src = slots["sources"]
            if not os.path.exists(self.p(src)):
                os.makedirs(self.p(src)); created.add(src.rstrip("/") + "/")

        # 4. hosts
        adapters = set(prev.get("adapters", []))
        if "claude-code" in hosts:
            self.install_claude(created); adapters.add("claude-code")
        if "gemini" in hosts:
            adapters.add("gemini")
        if "hermes" in hosts and hermes_home:
            self.install_hermes(hermes_home); adapters.add("hermes")
            prev_h = prev.get("hermes_home")
            if prev_h and prev_h != hermes_home:
                self.log.append(f"note: hermes plugin also left in {prev_h}")
            kits_hermes = hermes_home
        else:
            kits_hermes = prev.get("hermes_home")

        entry = {"version": VERSION, "installed": prev.get("installed") or dt.date.today().isoformat(),
                 "adapters": sorted(adapters), "created": sorted(created), "template_hashes": hashes,
                 "placement": self._modes}
        if kits_hermes:
            entry["hermes_home"] = kits_hermes
        kits["frugal-bridge"] = entry
        self.save_kits(k)
        return self.check(), self.log

    def install_claude(self, created):
        # hook script lives inside the project so its path is stable; settings merged key by key
        hook_src = os.path.join(ROOT, "adapters", "claude-code", "frugal_hook.py")
        dst = self.p(HOOK_MARK)
        new = open(hook_src).read()
        if read(dst) != new:
            write(dst, new); os.chmod(dst, 0o755)
        for sk in sorted(os.listdir(os.path.join(KIT, "skills"))):
            s_src = os.path.join(KIT, "skills", sk, "SKILL.md"); rel = f".claude/skills/{sk}/SKILL.md"
            body = open(s_src).read()
            if read(self.p(rel)) != body:
                write(self.p(rel), body)
        cmd = f'python3 "{dst}"'
        rel = ".claude/settings.json"
        t = read(self.p(rel))
        try:
            data = json.loads(t) if t and t.strip() else {}
        except json.JSONDecodeError:
            raise SystemExit(f"{rel} is not valid JSON; fix it by hand first (nothing changed there).")
        if t is None:
            created.add(rel)
        hooks = data.setdefault("hooks", {})
        for ev in ("SessionStart", "UserPromptSubmit"):
            lst = hooks.setdefault(ev, [])
            lst[:] = [g for g in lst if not self._is_ours(g)]   # replace our old entry (path/version change)
            lst.append({"hooks": [{"type": "command", "command": cmd}]})
        self.change(rel, json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    @staticmethod
    def _is_ours(group):
        return any(HOOK_MARK in (h.get("command") or "") for h in (group.get("hooks") or []) if isinstance(h, dict))

    def install_hermes(self, home):
        dst = os.path.join(home, "plugins", "frugal-bridge")
        shutil.copytree(os.path.join(ROOT, "adapters", "hermes", "frugal-bridge"), dst, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
        cfgp = os.path.join(home, "frugal-bridge", "config.json")
        cfg = json.loads(read(cfgp) or "{}")
        cfg["base_dir"] = self.d
        write(cfgp, json.dumps(cfg, indent=2) + "\n")
        self.log.append(f"hermes plugin copied to {dst}; enable with: hermes plugins enable frugal-bridge (then restart the gateway)")

    # ---------------------------------------------------------------- uninstall
    def uninstall(self):
        k = self.kits()
        kits = k.get("kits", {})
        me = kits.get("frugal-bridge")
        if not me:
            return ["frugal-bridge not installed here (nothing changed)"]
        created = set(me.get("created", []))
        hashes = me.get("template_hashes", {})
        base = "base-folder" in kits
        kept = []
        modes = me.get("placement", {})

        # blocks
        for rel in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
            t = read(self.p(rel))
            if t is None:
                continue
            new, had = self.strip_block(t, modes.get(rel))
            if rel in created and rel != "AGENTS.md" and new.strip() == POINTER and not base:
                self.backup(rel); os.remove(self.p(rel)); self.log.append(f"removed {rel}"); continue
            if had:
                if rel in created and not new.strip():
                    self.backup(rel); os.remove(self.p(rel)); self.log.append(f"removed {rel}")
                else:
                    self.change(rel, new)

        # claude settings / hook / skills
        rel = ".claude/settings.json"
        t = read(self.p(rel))
        if t:
            data = json.loads(t)
            hooks = data.get("hooks", {})
            for ev in list(hooks):
                hooks[ev] = [g for g in hooks[ev] if not self._is_ours(g)]
                if not hooks[ev]:
                    del hooks[ev]
            if not hooks:
                data.pop("hooks", None)
            if not data and rel in created:
                self.backup(rel); os.remove(self.p(rel))
            else:
                self.change(rel, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        for sk in os.listdir(os.path.join(KIT, "skills")):
            shutil.rmtree(self.p(f".claude/skills/{sk}"), ignore_errors=True)
        for d in (".claude/skills", ".claude"):
            if os.path.isdir(self.p(d)) and not os.listdir(self.p(d)):
                os.rmdir(self.p(d))
        if os.path.exists(self.p(HOOK_MARK)):
            os.remove(self.p(HOOK_MARK))

        # hermes plugin copy (not enabled/disabled here)
        h = me.get("hermes_home")
        if h:
            shutil.rmtree(os.path.join(h, "plugins", "frugal-bridge"), ignore_errors=True)
            self.log.append("hermes plugin folder removed; also run: hermes plugins disable frugal-bridge")

        # slot files we created: remove only if untouched and no base owns slots
        for rel in sorted(created):
            if rel in ("AGENTS.md", "CLAUDE.md", "GEMINI.md", ".claude/settings.json"):
                continue
            full = self.p(rel)
            if rel.endswith("/"):
                if os.path.isdir(full) and not os.listdir(full) and not base:
                    os.rmdir(full)
                elif os.path.isdir(full):
                    kept.append(rel)
                continue
            if not os.path.exists(full):
                continue
            if not base and sha(open(full, encoding="utf-8").read()) == hashes.get(rel):
                os.remove(full)
            else:
                kept.append(rel)
        if kept:
            self.log.append("kept (has your content or a base folder uses it): " + ", ".join(kept))

        # registry
        del kits["frugal-bridge"]
        if not base:
            mine = {v for v in DEFAULT_SLOTS.values()}
            for s, v in list(k.get("slots", {}).items()):
                if v in mine and v not in kept and not os.path.exists(self.p(v)):
                    del k["slots"][s]
            if not k.get("slots"):
                k.pop("slots", None)
        if not kits and not k.get("slots") and set(k) <= {"kits", "slots"}:
            self.backup(".kits.json"); os.remove(self.p(".kits.json"))
        else:
            self.save_kits(k)
        fb = self.p(".frugal-bridge")
        if os.path.isdir(fb) and not os.listdir(fb):
            os.rmdir(fb)  # backups (if any) are kept
        return self.log

    # ---------------------------------------------------------------- check
    def check(self):
        out, ok = [], True
        t = read(self.p("AGENTS.md")) or ""
        n = len(START_RE.findall(t))
        out.append(f"AGENTS.md frugal block: {n}"); ok &= n == 1
        b = len(t.encode())
        if b > CODEX_LIMIT:
            out.append(f"AGENTS.md size {b} bytes > {CODEX_LIMIT} (Codex reads only the first 32 KiB): shorten a block"); ok = False
        elif b > SOFT_LIMIT:
            out.append(f"AGENTS.md size {b} bytes: close to the 32 KiB Codex limit")
        else:
            out.append(f"AGENTS.md size {b} bytes (limit {CODEX_LIMIT})")
        if "<!-- base-folder:start" in t and t.find("<!-- base-folder:start") > (START_RE.search(t).start() if n else 1e9):
            out.append("order: frugal block is before the base block (should be after)"); ok = False
        for rel in ("CLAUDE.md", "GEMINI.md"):
            c = read(self.p(rel))
            if c is not None:
                has = any(l.strip() == POINTER for l in c.splitlines())
                out.append(f"{rel} imports AGENTS.md: {has}"); ok &= has
        k = self.kits()
        for s, v in (k.get("slots") or {}).items():
            if s in ("user", "now") and not os.path.exists(self.p(v)):
                out.append(f"slot {s} -> {v}: missing"); ok = False
        out.insert(0, "OK" if ok else "PROBLEMS")
        return "\n".join(out)


def main(argv):
    if len(argv) < 3 or argv[1] not in ("install", "uninstall", "check"):
        print(__doc__); return 2
    s = Setup(argv[2])
    hosts = ("claude-code", "gemini")
    home = None
    if "--hosts" in argv:
        hosts = tuple(argv[argv.index("--hosts") + 1].split(","))
    if "--hermes-home" in argv:
        home = argv[argv.index("--hermes-home") + 1]
    elif "hermes" in hosts:
        home = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    if argv[1] == "install":
        rep, log = s.install(hosts, home)
        print("\n".join(log)); print(rep)
        return 0 if rep.startswith("OK") else 1
    if argv[1] == "uninstall":
        print("\n".join(s.uninstall())); return 0
    rep = s.check(); print(rep)
    return 0 if rep.startswith("OK") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
