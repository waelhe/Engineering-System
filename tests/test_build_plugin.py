import json
import subprocess
from pathlib import Path

import tools.build_plugin as build_plugin
from tools.build_plugin import copy_overlay, register_claude_agents, update_manifest


def test_manifest_identity_and_openai_surface_are_rebranded(tmp_path: Path):
    path = tmp_path / "plugin.json"
    path.write_text(json.dumps({
        "name": "egm",
        "version": "0.1.1",
        "extensions": {"com.openai": {"interface": {"displayName": "Elephant-Goldfish Model"}}}
    }), encoding="utf-8")
    update_manifest(path)
    result = json.loads(path.read_text(encoding="utf-8"))
    assert result["name"] == "egm-engineering-system"
    assert result["version"] == "0.1.0"
    assert result["extensions"]["com.openai"]["interface"]["displayName"] == "EGM Engineering System"
    assert result["extensions"]["com.openai"]["interface"]["defaultPrompt"]


def test_overlay_adds_and_replaces_without_deleting_upstream_files(tmp_path: Path):
    source = tmp_path / "overlay"
    destination = tmp_path / "runtime"
    (source / "skills" / "new-skill").mkdir(parents=True)
    (source / "skills" / "new-skill" / "SKILL.md").write_text("local skill", encoding="utf-8")
    (source / "resources").mkdir()
    (source / "resources" / "execution_instructions.md").write_text("local charter", encoding="utf-8")
    (destination / "skills" / "upstream-skill").mkdir(parents=True)
    (destination / "skills" / "upstream-skill" / "SKILL.md").write_text("upstream", encoding="utf-8")
    (destination / "resources").mkdir()
    (destination / "resources" / "execution_instructions.md").write_text("upstream charter", encoding="utf-8")
    copy_overlay(source, destination)
    assert (destination / "skills/new-skill/SKILL.md").read_text(encoding="utf-8") == "local skill"
    assert (destination / "skills/upstream-skill/SKILL.md").read_text(encoding="utf-8") == "upstream"
    assert (destination / "resources/execution_instructions.md").read_text(encoding="utf-8") == "local charter"


def test_host_manifest_without_openai_interface_stays_host_neutral(tmp_path: Path):
    path = tmp_path / "plugin.json"
    path.write_text(json.dumps({"name": "egm", "version": "0.1.1"}), encoding="utf-8")
    update_manifest(path)
    result = json.loads(path.read_text(encoding="utf-8"))
    assert result["name"] == "egm-engineering-system"
    assert "extensions" not in result


def test_export_uses_pinned_git_tree_not_mutable_worktree(tmp_path: Path, monkeypatch):
    upstream = tmp_path / "upstream"
    upstream.mkdir()

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(upstream), *args],
            check=True, capture_output=True, text=True,
        )

    git("init")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.invalid")
    (upstream / "scripts").mkdir()
    packer = upstream / "scripts" / "pack_plugin.py"
    packer.write_text("print('pinned')\\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "pinned baseline")
    commit = git("rev-parse", "HEAD").stdout.strip()

    packer.write_text("print('modified worktree')\\n", encoding="utf-8")
    (upstream / "scripts" / "untracked.py").write_text("raise RuntimeError()\\n", encoding="utf-8")
    monkeypatch.setattr(build_plugin, "UPSTREAM", upstream)
    destination = tmp_path / "exported"

    build_plugin.export_pinned_upstream(destination, commit)

    assert (destination / "scripts" / "pack_plugin.py").read_text(encoding="utf-8") == "print('pinned')\\n"
    assert not (destination / "scripts" / "untracked.py").exists()


def test_claude_manifest_registers_agents_from_plugin_root(tmp_path: Path):
    stage = tmp_path / "stage"
    manifest_directory = stage / ".claude-plugin"
    upstream_agents = manifest_directory / "agents"
    root_agents = stage / "agents"
    adapters = tmp_path / "adapters"
    upstream_agents.mkdir(parents=True)
    root_agents.mkdir(parents=True)
    adapters.mkdir(parents=True)

    upstream_names = ("comprehension.md", "design_critic.md", "bootstrap_orchestrator.md")
    for name in upstream_names:
        (upstream_agents / name).write_text("upstream agent", encoding="utf-8")
    (root_agents / "bootstrap_orchestrator.md").write_text("existing root agent", encoding="utf-8")
    local_names = (
        ("implementation-verifier.md", "egm-implementation-verifier.md"),
        ("knowledge-integrity-auditor.md", "egm-knowledge-integrity-auditor.md"),
        ("root-cause-investigator.md", "egm-root-cause-investigator.md"),
    )
    for source_name, _ in local_names:
        (adapters / source_name).write_text("local adapter", encoding="utf-8")

    manifest = manifest_directory / "plugin.json"
    manifest.write_text(json.dumps({
        "agents": [f"./.claude-plugin/agents/{name}" for name in upstream_names]
    }), encoding="utf-8")

    register_claude_agents(manifest, root_agents, adapters)

    refs = json.loads(manifest.read_text(encoding="utf-8"))["agents"]
    assert refs == [
        "./agents/comprehension.md",
        "./agents/design_critic.md",
        "./agents/egm-upstream-bootstrap_orchestrator.md",
        "./agents/egm-implementation-verifier.md",
        "./agents/egm-knowledge-integrity-auditor.md",
        "./agents/egm-root-cause-investigator.md",
    ]
    assert all((root_agents / name).is_file() for name in upstream_names if name != "bootstrap_orchestrator.md")
    assert (root_agents / "bootstrap_orchestrator.md").read_text(encoding="utf-8") == "existing root agent"
    assert (root_agents / "egm-upstream-bootstrap_orchestrator.md").read_text(encoding="utf-8") == "upstream agent"
    assert all((root_agents / target_name).is_file() for _, target_name in local_names)
    assert not upstream_agents.exists() or not any(upstream_agents.iterdir())
