"""Tests for kit/setup.py (coexistence contract). Run: pytest -q kit/test_setup.py"""
import hashlib, importlib.util, json, os, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("setup_kit", os.path.join(HERE, "setup.py"))
S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)


def tree(d, skip=(".frugal-bridge/backup",)):
    out = {}
    for root, dirs, files in os.walk(d):
        rel = os.path.relpath(root, d)
        if any(rel == s or rel.startswith(s + os.sep) for s in skip):
            continue
        for f in files:
            p = os.path.join(root, f)
            out[os.path.relpath(p, d)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
        for x in dirs:
            out.setdefault(os.path.relpath(os.path.join(root, x), d) + "/", "dir")
    return out


def strip_dirs(t):
    return {k: v for k, v in t.items() if v != "dir" and not k.startswith(".frugal-bridge/backup")}


def inst(d, **kw):
    return S.Setup(str(d)).install(**kw)


def test_fresh_install(tmp_path):
    rep, _ = inst(tmp_path)
    assert rep.startswith("OK"), rep
    a = (tmp_path / "AGENTS.md").read_text()
    assert a.count("<!-- frugal-bridge:start") == 1 and a.count("<!-- frugal-bridge:end -->") == 1
    assert (tmp_path / "CLAUDE.md").read_text() == "@AGENTS.md\n"
    assert (tmp_path / "GEMINI.md").read_text() == "@AGENTS.md\n"
    k = json.loads((tmp_path / ".kits.json").read_text())
    assert k["slots"]["now"] == "PROGRESS.md" and (tmp_path / "PROGRESS.md").exists() and (tmp_path / "USER.md").exists()
    st = json.loads((tmp_path / ".claude/settings.json").read_text())
    assert any(S.HOOK_MARK in h["command"] for g in st["hooks"]["SessionStart"] for h in g["hooks"])
    assert (tmp_path / ".claude/skills/frugal-handoff/SKILL.md").exists()


def test_rerun_is_byte_identical(tmp_path):
    inst(tmp_path); t1 = tree(tmp_path)
    inst(tmp_path); t2 = tree(tmp_path)
    assert strip_dirs(t1) == strip_dirs(t2)


def test_install_uninstall_restores_empty(tmp_path):
    before = strip_dirs(tree(tmp_path))
    inst(tmp_path); S.Setup(str(tmp_path)).uninstall()
    assert strip_dirs(tree(tmp_path)) == before


def test_user_text_kept_byte_identical(tmp_path):
    for content in ("# My rules\nbe nice\n", "no newline at end", "two newlines\n\n"):
        d = tmp_path / str(abs(hash(content))); d.mkdir()
        (d / "AGENTS.md").write_text(content); (d / "CLAUDE.md").write_text("my claude notes\n")
        inst(d)
        a = (d / "AGENTS.md").read_text()
        assert a.startswith(content.rstrip("\n")) and a.count("frugal-bridge:start") == 1
        c = (d / "CLAUDE.md").read_text()
        assert c.startswith("my claude notes\n") and "@AGENTS.md" in c
        S.Setup(str(d)).uninstall()
        assert (d / "AGENTS.md").read_text() == content
        assert (d / "CLAUDE.md").read_text() == "my claude notes\n"


def test_existing_pointer_left_alone(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("@AGENTS.md\nextra\n")
    inst(tmp_path)
    assert (tmp_path / "CLAUDE.md").read_text() == "@AGENTS.md\nextra\n"


def test_json_merge_keeps_other_hooks_and_keys(tmp_path):
    other = {"model": "x", "permissions": {"allow": ["Bash(ls)"]},
             "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "my-own.sh"}]}],
                       "PostToolUse": [{"matcher": "Edit", "hooks": [{"type": "command", "command": "fmt.sh"}]}]}}
    (tmp_path / ".claude").mkdir(); (tmp_path / ".claude/settings.json").write_text(json.dumps(other))
    inst(tmp_path); inst(tmp_path)   # twice: no duplicate entries
    st = json.loads((tmp_path / ".claude/settings.json").read_text())
    ss = st["hooks"]["SessionStart"]
    assert sum(1 for g in ss for h in g["hooks"] if S.HOOK_MARK in h["command"]) == 1
    assert any(h["command"] == "my-own.sh" for g in ss for h in g["hooks"])
    assert st["model"] == "x" and st["hooks"]["PostToolUse"] == other["hooks"]["PostToolUse"]
    S.Setup(str(tmp_path)).uninstall()
    assert json.loads((tmp_path / ".claude/settings.json").read_text()) == other


def test_invalid_json_settings_refused(tmp_path):
    (tmp_path / ".claude").mkdir(); (tmp_path / ".claude/settings.json").write_text("{ not json")
    try:
        inst(tmp_path)
        assert False, "should refuse"
    except SystemExit as e:
        assert "not valid JSON" in str(e)
    assert (tmp_path / ".claude/settings.json").read_text() == "{ not json"


def base_folder(d):
    (d / "wiki/me").mkdir(parents=True); (d / "wiki/me/README.md").write_text("me\n"); (d / "hot.md").write_text("now\n")
    (d / "AGENTS.md").write_text("intro\n\n<!-- base-folder:start v1 -->\nbase rules\n<!-- base-folder:end -->\n\nmy tail\n")
    k = {"kits": {"base-folder": {"version": "1"}},
         "slots": {"user": "wiki/me/README.md", "now": "hot.md", "decisions": "wiki/decisions/", "map": "wiki/index.md", "sources": "raw/"}}
    (d / ".kits.json").write_text(json.dumps(k, indent=2) + "\n")


def test_base_first_then_frugal(tmp_path):
    base_folder(tmp_path)
    before = (tmp_path / "AGENTS.md").read_text()
    rep, _ = inst(tmp_path)
    assert rep.startswith("OK"), rep
    for f in ("USER.md", "PROGRESS.md", "DECISIONS.md", "sources"):
        assert not (tmp_path / f).exists(), f
    a = (tmp_path / "AGENTS.md").read_text()
    assert a.index("base-folder:end") < a.index("frugal-bridge:start") < a.index("my tail")
    k = json.loads((tmp_path / ".kits.json").read_text())
    assert k["slots"]["now"] == "hot.md" and "base-folder" in k["kits"]
    S.Setup(str(tmp_path)).uninstall()
    assert (tmp_path / "AGENTS.md").read_text() == before
    k = json.loads((tmp_path / ".kits.json").read_text())
    assert "frugal-bridge" not in k["kits"] and k["slots"]["now"] == "hot.md"
    assert (tmp_path / "hot.md").read_text() == "now\n"


def test_uninstall_keeps_edited_slot_files(tmp_path):
    inst(tmp_path)
    (tmp_path / "USER.md").write_text("my real preferences\n")
    log = S.Setup(str(tmp_path)).uninstall()
    assert (tmp_path / "USER.md").read_text() == "my real preferences\n"
    assert any("kept" in l and "USER.md" in l for l in log)
    assert not (tmp_path / "PROGRESS.md").exists()


def test_old_version_without_registry(tmp_path):
    (tmp_path / "AGENTS.md").write_text("<!-- frugal-bridge:start v5 -->\nold rules\n<!-- frugal-bridge:end -->\n")
    rep, _ = inst(tmp_path)
    a = (tmp_path / "AGENTS.md").read_text()
    assert a.count("frugal-bridge:start") == 1 and "v6" in a and "old rules" not in a
    assert "frugal-bridge" in json.loads((tmp_path / ".kits.json").read_text())["kits"]


def test_size_check_flags_codex_limit(tmp_path):
    base_folder(tmp_path)
    a = (tmp_path / "AGENTS.md").read_text().replace("base rules", "x" * 30000)
    (tmp_path / "AGENTS.md").write_text(a)
    rep, _ = inst(tmp_path)
    assert rep.startswith("PROBLEMS") and "32768" in rep


def test_hermes_copy(tmp_path):
    home = tmp_path / "hh"; proj = tmp_path / "p"
    inst(proj, hosts=("hermes",), hermes_home=str(home))
    assert (home / "plugins/frugal-bridge/__init__.py").exists()
    assert json.loads((home / "frugal-bridge/config.json").read_text())["base_dir"] == str(proj)
    assert not (proj / "CLAUDE.md").exists()
    S.Setup(str(proj)).uninstall()
    assert not (home / "plugins/frugal-bridge").exists()
