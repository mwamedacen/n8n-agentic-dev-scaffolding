"""Tests for helpers/placeholder/py_resolver.py."""
import json
from pathlib import Path

import pytest

from helpers.placeholder import py_resolver


CALC_STATS_PY = '''def calculate_stats_by_category(articles):
    """Group articles by category and count them.

    Returns a dict of {category: count}.
    """
    stats = {}
    for article in articles:
        cat = article.get("category", "uncategorized")
        stats[cat] = stats.get(cat, 0) + 1
    return stats
'''


def _workflow_json(py_code: str) -> str:
    return json.dumps(
        {
            "name": "Smoke",
            "nodes": [
                {
                    "name": "Code",
                    "type": "n8n-nodes-base.code",
                    "parameters": {"language": "python", "pythonCode": py_code},
                }
            ],
            "connections": {},
            "settings": {},
        },
        indent=2,
    )


def test_multiline_python_with_docstring_produces_valid_json(tmp_path):
    """Multi-line Python with triple-quoted docstring + indentation must hydrate into valid JSON."""
    fn_dir = tmp_path / "n8n-functions" / "py"
    fn_dir.mkdir(parents=True)
    py_file = fn_dir / "calculate_stats_by_category.py"
    py_file.write_text(CALC_STATS_PY)

    raw = _workflow_json("{{@:py:n8n-functions/py/calculate_stats_by_category.py}}")
    out = py_resolver.resolve(raw, tmp_path)

    data = json.loads(out)
    code = data["nodes"][0]["parameters"]["pythonCode"]
    assert "def calculate_stats_by_category(articles):" in code
    assert '"""Group articles by category and count them.' in code
    assert "stats[cat] = stats.get(cat, 0) + 1" in code
    # Resolver writes `MATCH` markers (Python has no `#` alias).
    assert "# MATCH:py:n8n-functions/py/calculate_stats_by_category.py" in code
    assert "# /MATCH:py:n8n-functions/py/calculate_stats_by_category.py" in code


def test_canonical_INTERPOLATE_form_also_accepted(tmp_path):
    fn_dir = tmp_path / "n8n-functions" / "py"
    fn_dir.mkdir(parents=True)
    (fn_dir / "calculate_stats_by_category.py").write_text(CALC_STATS_PY)

    raw = _workflow_json("{{INTERPOLATE:py:n8n-functions/py/calculate_stats_by_category.py}}")
    out = py_resolver.resolve(raw, tmp_path)
    data = json.loads(out)
    assert "def calculate_stats_by_category(articles):" in data["nodes"][0]["parameters"]["pythonCode"]


def test_legacy_HYDRATE_form_no_longer_substitutes(tmp_path):
    """Hard cutover: `{{HYDRATE:py:...}}` is NOT recognized; placeholder passes through unchanged."""
    fn_dir = tmp_path / "n8n-functions" / "py"
    fn_dir.mkdir(parents=True)
    (fn_dir / "calculate_stats_by_category.py").write_text(CALC_STATS_PY)

    raw = _workflow_json("{{HYDRATE:py:n8n-functions/py/calculate_stats_by_category.py}}")
    out = py_resolver.resolve(raw, tmp_path)
    data = json.loads(out)
    assert "{{HYDRATE:py:" in data["nodes"][0]["parameters"]["pythonCode"]


def test_glue_survives_hydrate(tmp_path):
    """A pythonCode field with a placeholder + n8n glue should keep the glue intact."""
    fn_dir = tmp_path / "n8n-functions" / "py"
    fn_dir.mkdir(parents=True)
    (fn_dir / "calculate_stats_by_category.py").write_text(CALC_STATS_PY)

    glue = (
        "{{@:py:n8n-functions/py/calculate_stats_by_category.py}}\n"
        "\n"
        'body = items[0]["json"]\n'
        'articles = body.get("articles", [])\n'
        "stats = calculate_stats_by_category(articles)\n"
        'return [{"json": {"stats": stats}}]\n'
    )
    raw = _workflow_json(glue)
    out = py_resolver.resolve(raw, tmp_path)

    data = json.loads(out)
    code = data["nodes"][0]["parameters"]["pythonCode"]
    assert 'body = items[0]["json"]' in code
    assert "stats = calculate_stats_by_category(articles)" in code
    assert 'return [{"json": {"stats": stats}}]' in code


def test_round_trip_restores_placeholder_and_glue(tmp_path):
    """hydrate → dehydrate restores the @-form placeholder; glue is preserved verbatim."""
    fn_dir = tmp_path / "n8n-functions" / "py"
    fn_dir.mkdir(parents=True)
    (fn_dir / "calculate_stats_by_category.py").write_text(CALC_STATS_PY)

    glue = (
        "{{@:py:n8n-functions/py/calculate_stats_by_category.py}}\n"
        "\n"
        'articles = items[0]["json"].get("articles", [])\n'
        'return [{"json": {"stats": calculate_stats_by_category(articles)}}]\n'
    )
    raw = _workflow_json(glue)
    hydrated = py_resolver.resolve(raw, tmp_path)
    dehydrated = py_resolver.dehydrate(hydrated)

    data = json.loads(dehydrated)
    code = data["nodes"][0]["parameters"]["pythonCode"]
    assert "{{@:py:n8n-functions/py/calculate_stats_by_category.py}}" in code
    assert 'articles = items[0]["json"].get("articles", [])' in code
    assert 'return [{"json": {"stats": calculate_stats_by_category(articles)}}]' in code
    assert "# MATCH:py:" not in code
    assert "# DEHYDRATE:py:" not in code


def test_legacy_DEHYDRATE_marker_collapses_on_dehydrate(tmp_path):
    """A workflow with the old `# DEHYDRATE:py:...` markers must still collapse back to a `{{@:py:...}}` placeholder."""
    rel_path = "n8n-functions/py/calculate_stats_by_category.py"
    legacy_pycode = (
        f"# DEHYDRATE:py:{rel_path}\n"
        + CALC_STATS_PY.rstrip("\n") + "\n"
        + f"# /DEHYDRATE:py:{rel_path}\n"
        "\n"
        'return [{"json": {}}]'
    )
    raw = _workflow_json(legacy_pycode)
    dehydrated = py_resolver.dehydrate(raw)
    code = json.loads(dehydrated)["nodes"][0]["parameters"]["pythonCode"]
    assert "{{@:py:" + rel_path + "}}" in code
    assert "# DEHYDRATE:py:" not in code


def test_resolve_raises_on_legacy_DEHYDRATE_marker_collision(tmp_path):
    """A Python source file containing a legacy `# DEHYDRATE:py:` substring must abort resolve()."""
    fn_dir = tmp_path / "n8n-functions" / "py"
    fn_dir.mkdir(parents=True)
    (fn_dir / "naughty.py").write_text(
        "def f():\n"
        "    # DEHYDRATE:py:somewhere this is bad\n"
        "    return 1\n"
    )
    raw = _workflow_json("{{@:py:n8n-functions/py/naughty.py}}")
    with pytest.raises(ValueError, match="MATCH/DEHYDRATE marker"):
        py_resolver.resolve(raw, tmp_path)


def test_resolve_raises_on_close_marker_collision(tmp_path):
    fn_dir = tmp_path / "n8n-functions" / "py"
    fn_dir.mkdir(parents=True)
    (fn_dir / "naughty.py").write_text("# /DEHYDRATE:py:trailing\n")
    raw = _workflow_json("{{@:py:n8n-functions/py/naughty.py}}")
    with pytest.raises(ValueError, match="MATCH/DEHYDRATE marker"):
        py_resolver.resolve(raw, tmp_path)


def test_resolve_raises_on_new_MATCH_marker_collision(tmp_path):
    """A Python source file containing the new `# MATCH:py:` substring must also abort resolve()."""
    fn_dir = tmp_path / "n8n-functions" / "py"
    fn_dir.mkdir(parents=True)
    (fn_dir / "naughty.py").write_text(
        "def f():\n"
        "    # MATCH:py:somewhere this is bad\n"
        "    return 1\n"
    )
    raw = _workflow_json("{{@:py:n8n-functions/py/naughty.py}}")
    with pytest.raises(ValueError, match="MATCH/DEHYDRATE marker"):
        py_resolver.resolve(raw, tmp_path)


def test_dehydrate_leaves_unrelated_strings_alone(tmp_path):
    raw = json.dumps(
        {
            "name": "Smoke",
            "nodes": [
                {
                    "name": "Set",
                    "type": "n8n-nodes-base.set",
                    "parameters": {"value": "hello # this is fine"},
                }
            ],
            "connections": {},
            "settings": {},
        },
        indent=2,
    )
    out = py_resolver.dehydrate(raw)
    data = json.loads(out)
    assert data["nodes"][0]["parameters"]["value"] == "hello # this is fine"


def test_resolve_rejects_absolute_paths(tmp_path):
    raw = _workflow_json("{{@:py:/abs/path.py}}")
    with pytest.raises(ValueError, match="Absolute paths"):
        py_resolver.resolve(raw, tmp_path)


def test_resolve_raises_on_missing_file(tmp_path):
    raw = _workflow_json("{{@:py:n8n-functions/py/missing.py}}")
    with pytest.raises(FileNotFoundError):
        py_resolver.resolve(raw, tmp_path)


def test_hydrate_dehydrate_full_round_trip(tmp_path):
    """End-to-end: helpers.hydrate.hydrate() then helpers.dehydrate.dehydrate_data() restores the placeholder."""
    import yaml

    ws = tmp_path / "ws"
    (ws / "n8n-config").mkdir(parents=True)
    (ws / "n8n-workflows-template").mkdir()
    (ws / "n8n-functions" / "py").mkdir(parents=True)

    (ws / "n8n-functions" / "py" / "calculate_stats_by_category.py").write_text(CALC_STATS_PY)

    yaml_data = {
        "name": "dev",
        "displayName": "Development",
        "n8n": {"instanceName": "localhost:8080"},
        "credentials": {},
        "workflows": {"smoke": {"id": "wf-1", "name": "Smoke"}},
    }
    (ws / "n8n-config" / "dev.yml").write_text(yaml.dump(yaml_data))
    (ws / "n8n-config" / ".env.dev").write_text("N8N_API_KEY=fake\n")

    glue = (
        "{{@:py:n8n-functions/py/calculate_stats_by_category.py}}\n"
        "\n"
        'body = items[0]["json"]\n'
        'articles = body.get("articles", [])\n'
        "stats = calculate_stats_by_category(articles)\n"
        'return [{"json": {"stats": stats}}]\n'
    )
    template = {
        "name": "Smoke",
        "nodes": [
            {
                "id": "{{@:uuid:code-id}}",
                "name": "Code",
                "type": "n8n-nodes-base.code",
                "parameters": {"language": "python", "pythonCode": glue},
            }
        ],
        "connections": {},
        "settings": {},
    }
    template_path = ws / "n8n-workflows-template" / "smoke.template.json"
    template_path.write_text(json.dumps(template, indent=2))

    from helpers.hydrate import hydrate
    from helpers.dehydrate import dehydrate_data

    built_path = hydrate("dev", "smoke", ws)
    built = json.loads(built_path.read_text())

    code_after_hydrate = built["nodes"][0]["parameters"]["pythonCode"]
    assert "def calculate_stats_by_category(articles):" in code_after_hydrate
    # Residual catcher: no INTERPOLATE/@/HYDRATE form should survive a successful hydrate.
    built_text = json.dumps(built)
    assert "{{INTERPOLATE" not in built_text
    assert "{{@:" not in built_text
    assert "{{HYDRATE" not in built_text

    live_returned = dict(built)
    live_returned["id"] = "wf-1"
    live_returned["active"] = True
    live_returned["versionId"] = "v1"
    live_returned["tags"] = []

    dehydrated_text = dehydrate_data(live_returned, "dev", ws, "smoke")
    round_tripped = json.loads(dehydrated_text)
    code_after_dehydrate = round_tripped["nodes"][0]["parameters"]["pythonCode"]

    assert "{{@:py:n8n-functions/py/calculate_stats_by_category.py}}" in code_after_dehydrate
    assert 'body = items[0]["json"]' in code_after_dehydrate
    assert "# MATCH:py:" not in code_after_dehydrate
    assert "# DEHYDRATE:py:" not in code_after_dehydrate
