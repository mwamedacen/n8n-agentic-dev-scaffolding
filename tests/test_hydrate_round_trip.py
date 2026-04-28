"""Tests for helpers/hydrate.py and helpers/validate.py."""
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml


def _harness() -> Path:
    return Path(__file__).parent.parent


def _make_workspace(tmp_path: Path, instance: str = "localhost:8080") -> Path:
    """Create a minimal workspace with a dev env and one template."""
    ws = tmp_path / "ws"
    (ws / "n8n-config").mkdir(parents=True)
    (ws / "n8n-workflows-template").mkdir()

    yaml_data = {
        "name": "dev",
        "displayName": "Development",
        "workflowNamePostfix": " [DEV]",
        "n8n": {"instanceName": instance},
        "credentials": {},
        "workflows": {
            "smoke": {"id": "abc-123", "name": "Smoke"},
        },
    }
    (ws / "n8n-config" / "dev.yml").write_text(yaml.dump(yaml_data))
    (ws / "n8n-config" / ".env.dev").write_text("N8N_API_KEY=fake\n")
    return ws


def run(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], capture_output=True, text=True)


class TestHydrate:
    def test_minimal_template_round_trip(self, tmp_path):
        """Hydrate a minimal template with env + uuid placeholders."""
        ws = _make_workspace(tmp_path)

        template = {
            "name": "Smoke {{@:env:displayName}}",
            "nodes": [
                {
                    "id": "{{@:uuid:trigger-id}}",
                    "name": "Trigger",
                    "type": "n8n-nodes-base.webhook",
                    "parameters": {"path": "smoke"},
                }
            ],
            "connections": {},
            "settings": {},
        }
        (ws / "n8n-workflows-template" / "smoke.template.json").write_text(json.dumps(template, indent=2))

        r = run(
            str(_harness() / "helpers" / "hydrate.py"),
            "--workspace", str(ws),
            "--env", "dev",
            "--workflow-key", "smoke",
        )
        assert r.returncode == 0, r.stderr
        out = ws / "n8n-build" / "dev" / "smoke.generated.json"
        assert out.is_file()
        text = out.read_text()
        assert "{{@:" not in text, "residual @ placeholder!"
        assert "{{INTERPOLATE" not in text, "residual INTERPOLATE placeholder!"
        assert "{{HYDRATE" not in text, "residual legacy HYDRATE placeholder!"
        data = json.loads(text)
        assert data["name"] == "Smoke Development"
        assert data["nodes"][0]["id"] != "{{@:uuid:trigger-id}}"

    def test_file_resolver_resolves_text(self, tmp_path):
        ws = _make_workspace(tmp_path)
        prompts_dir = ws / "n8n-prompts" / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "summary.txt").write_text("You are a summarizer.")

        template = {
            "name": "Smoke",
            "nodes": [
                {
                    "name": "Set",
                    "type": "n8n-nodes-base.set",
                    "parameters": {"prompt": "{{@:txt:n8n-prompts/prompts/summary.txt}}"},
                }
            ],
            "connections": {},
            "settings": {},
        }
        (ws / "n8n-workflows-template" / "smoke.template.json").write_text(json.dumps(template))

        r = run(
            str(_harness() / "helpers" / "hydrate.py"),
            "--workspace", str(ws),
            "--env", "dev",
            "--workflow-key", "smoke",
        )
        assert r.returncode == 0, r.stderr
        data = json.loads((ws / "n8n-build" / "dev" / "smoke.generated.json").read_text())
        assert data["nodes"][0]["parameters"]["prompt"] == "You are a summarizer."

    def test_uuid_resolver_consistent_within_template(self, tmp_path):
        ws = _make_workspace(tmp_path)
        template = {
            "name": "Smoke",
            "nodes": [
                {"id": "{{@:uuid:a}}", "name": "A", "type": "x", "parameters": {}},
                {"id": "{{@:uuid:a}}", "name": "B", "type": "x", "parameters": {}},
                {"id": "{{@:uuid:b}}", "name": "C", "type": "x", "parameters": {}},
            ],
            "connections": {},
            "settings": {},
        }
        (ws / "n8n-workflows-template" / "smoke.template.json").write_text(json.dumps(template))

        run(
            str(_harness() / "helpers" / "hydrate.py"),
            "--workspace", str(ws), "--env", "dev", "--workflow-key", "smoke",
        )
        data = json.loads((ws / "n8n-build" / "dev" / "smoke.generated.json").read_text())
        a_id, dup_id, b_id = data["nodes"][0]["id"], data["nodes"][1]["id"], data["nodes"][2]["id"]
        assert a_id == dup_id
        assert a_id != b_id

    def test_residual_placeholder_in_strict_fails(self, tmp_path):
        ws = _make_workspace(tmp_path)
        # Reference an env key that doesn't exist
        template = {
            "name": "{{@:env:does.not.exist}}",
            "nodes": [],
            "connections": {},
            "settings": {},
        }
        (ws / "n8n-workflows-template" / "smoke.template.json").write_text(json.dumps(template))

        r = run(
            str(_harness() / "helpers" / "hydrate.py"),
            "--workspace", str(ws), "--env", "dev", "--workflow-key", "smoke", "--strict",
        )
        assert r.returncode != 0


class TestValidate:
    def test_valid_template(self, tmp_path):
        ws = _make_workspace(tmp_path)
        template = {
            "name": "Smoke",
            "nodes": [{"name": "T", "type": "x", "parameters": {}}],
            "connections": {},
            "settings": {},
        }
        (ws / "n8n-workflows-template" / "smoke.template.json").write_text(json.dumps(template))

        r = run(
            str(_harness() / "helpers" / "validate.py"),
            "--workspace", str(ws),
            "--workflow-key", "smoke",
            "--source", "template",
        )
        assert r.returncode == 0
        result = json.loads(r.stdout)
        assert result["valid"] is True

    def test_missing_nodes_invalid(self, tmp_path):
        ws = _make_workspace(tmp_path)
        bad = {"connections": {}, "settings": {}}
        (ws / "n8n-workflows-template" / "smoke.template.json").write_text(json.dumps(bad))

        r = run(
            str(_harness() / "helpers" / "validate.py"),
            "--workspace", str(ws),
            "--workflow-key", "smoke",
            "--source", "template",
        )
        assert r.returncode == 1
        result = json.loads(r.stdout)
        assert result["valid"] is False

    def test_pindata_in_template_invalid(self, tmp_path):
        ws = _make_workspace(tmp_path)
        bad = {
            "name": "S",
            "nodes": [{"name": "T", "type": "x", "parameters": {}}],
            "connections": {},
            "settings": {},
            "pinData": {"T": [{"json": {}}]},
        }
        (ws / "n8n-workflows-template" / "smoke.template.json").write_text(json.dumps(bad))

        r = run(
            str(_harness() / "helpers" / "validate.py"),
            "--workspace", str(ws),
            "--workflow-key", "smoke",
            "--source", "template",
        )
        assert r.returncode == 1

    def test_residual_placeholder_in_built_invalid(self, tmp_path):
        ws = _make_workspace(tmp_path)
        build_dir = ws / "n8n-build" / "dev"
        build_dir.mkdir(parents=True)
        bad = {
            "name": "{{@:env:displayName}}",
            "nodes": [{"name": "T", "type": "x", "parameters": {}}],
            "connections": {},
            "settings": {},
        }
        (build_dir / "smoke.generated.json").write_text(json.dumps(bad))

        r = run(
            str(_harness() / "helpers" / "validate.py"),
            "--workspace", str(ws),
            "--env", "dev",
            "--workflow-key", "smoke",
            "--source", "built",
        )
        assert r.returncode == 1
