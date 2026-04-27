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

    raw = _workflow_json("{{HYDRATE:py:n8n-functions/py/calculate_stats_by_category.py}}")
    out = py_resolver.resolve(raw, tmp_path)

    data = json.loads(out)
    code = data["nodes"][0]["parameters"]["pythonCode"]
    assert "def calculate_stats_by_category(articles):" in code
    assert '"""Group articles by category and count them.' in code
    assert "stats[cat] = stats.get(cat, 0) + 1" in code
    assert "# DEHYDRATE:py:n8n-functions/py/calculate_stats_by_category.py" in code
    assert "# /DEHYDRATE:py:n8n-functions/py/calculate_stats_by_category.py" in code


def test_glue_survives_hydrate(tmp_path):
    """A pythonCode field with a placeholder + n8n glue should keep the glue intact."""
    fn_dir = tmp_path / "n8n-functions" / "py"
    fn_dir.mkdir(parents=True)
    (fn_dir / "calculate_stats_by_category.py").write_text(CALC_STATS_PY)

    glue = (
        "{{HYDRATE:py:n8n-functions/py/calculate_stats_by_category.py}}\n"
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
    """hydrate → dehydrate restores the original placeholder; glue is preserved verbatim."""
    fn_dir = tmp_path / "n8n-functions" / "py"
    fn_dir.mkdir(parents=True)
    (fn_dir / "calculate_stats_by_category.py").write_text(CALC_STATS_PY)

    glue = (
        "{{HYDRATE:py:n8n-functions/py/calculate_stats_by_category.py}}\n"
        "\n"
        'articles = items[0]["json"].get("articles", [])\n'
        'return [{"json": {"stats": calculate_stats_by_category(articles)}}]\n'
    )
    raw = _workflow_json(glue)
    hydrated = py_resolver.resolve(raw, tmp_path)
    dehydrated = py_resolver.dehydrate(hydrated)

    data = json.loads(dehydrated)
    code = data["nodes"][0]["parameters"]["pythonCode"]
    assert "{{HYDRATE:py:n8n-functions/py/calculate_stats_by_category.py}}" in code
    assert 'articles = items[0]["json"].get("articles", [])' in code
    assert 'return [{"json": {"stats": calculate_stats_by_category(articles)}}]' in code
    assert "# DEHYDRATE:py:" not in code


def test_resolve_raises_on_marker_collision(tmp_path):
    """A Python file containing the DEHYDRATE marker substring must abort resolve()."""
    fn_dir = tmp_path / "n8n-functions" / "py"
    fn_dir.mkdir(parents=True)
    (fn_dir / "naughty.py").write_text(
        "def f():\n"
        "    # DEHYDRATE:py:somewhere this is bad\n"
        "    return 1\n"
    )
    raw = _workflow_json("{{HYDRATE:py:n8n-functions/py/naughty.py}}")
    with pytest.raises(ValueError, match="DEHYDRATE marker"):
        py_resolver.resolve(raw, tmp_path)


def test_resolve_raises_on_close_marker_collision(tmp_path):
    fn_dir = tmp_path / "n8n-functions" / "py"
    fn_dir.mkdir(parents=True)
    (fn_dir / "naughty.py").write_text("# /DEHYDRATE:py:trailing\n")
    raw = _workflow_json("{{HYDRATE:py:n8n-functions/py/naughty.py}}")
    with pytest.raises(ValueError, match="DEHYDRATE marker"):
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
    raw = _workflow_json("{{HYDRATE:py:/abs/path.py}}")
    with pytest.raises(ValueError, match="Absolute paths"):
        py_resolver.resolve(raw, tmp_path)


def test_resolve_raises_on_missing_file(tmp_path):
    raw = _workflow_json("{{HYDRATE:py:n8n-functions/py/missing.py}}")
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
        "{{HYDRATE:py:n8n-functions/py/calculate_stats_by_category.py}}\n"
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
                "id": "{{HYDRATE:uuid:code-id}}",
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
    assert "{{HYDRATE" not in json.dumps(built), "no residual placeholders after hydrate"

    live_returned = dict(built)
    live_returned["id"] = "wf-1"
    live_returned["active"] = True
    live_returned["versionId"] = "v1"
    live_returned["tags"] = []

    dehydrated_text = dehydrate_data(live_returned, "dev", ws, "smoke")
    round_tripped = json.loads(dehydrated_text)
    code_after_dehydrate = round_tripped["nodes"][0]["parameters"]["pythonCode"]

    assert "{{HYDRATE:py:n8n-functions/py/calculate_stats_by_category.py}}" in code_after_dehydrate
    assert 'body = items[0]["json"]' in code_after_dehydrate
    assert "# DEHYDRATE:py:" not in code_after_dehydrate
