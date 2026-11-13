import json
from pathlib import Path

from tools.build_plugin import copy_overlay, update_manifest


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
