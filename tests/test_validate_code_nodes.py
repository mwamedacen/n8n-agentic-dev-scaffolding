"""Tests for the Code-node discipline rules in helpers/validate.py."""
import json
from pathlib import Path

import pytest

from helpers.validate import validate_workflow_json


CALC_STATS_JS_OK = '''function calculateStatsByCategory(articles) {
  const stats = {};
  for (const article of articles) {
    const cat = article.category || "uncategorized";
    stats[cat] = (stats[cat] || 0) + 1;
  }
  return stats;
}
if (typeof module !== "undefined") module.exports = { calculateStatsByCategory };
'''

CALC_STATS_JS_NO_TRAILER = '''function calculateStatsByCategory(articles) {
  return articles;
}
'''

CALC_STATS_PY_OK = '''def calculate_stats_by_category(articles):
    return {}
'''


def _wrap(node: dict) -> str:
    """Wrap a single node in a minimally valid workflow document and serialize."""
    return json.dumps(
        {
            "name": "Smoke",
            "nodes": [node],
            "connections": {},
            "settings": {},
        },
        indent=2,
    )


def _seed_js(ws: Path, with_trailer: bool = True, with_test: bool = True) -> None:
    fn_dir = ws / "n8n-functions" / "js"
    fn_dir.mkdir(parents=True)
    (fn_dir / "calculateStatsByCategory.js").write_text(
        CALC_STATS_JS_OK if with_trailer else CALC_STATS_JS_NO_TRAILER
    )
    if with_test:
        (ws / "n8n-functions-tests").mkdir()
        (ws / "n8n-functions-tests" / "calculateStatsByCategory.test.js").write_text(
            'const { test } = require("node:test");\n'
            'const assert = require("node:assert/strict");\n'
            'const { calculateStatsByCategory } = require("../n8n-functions/js/calculateStatsByCategory.js");\n'
            'test("noop", () => { assert.deepEqual(calculateStatsByCategory([]), {}); });\n'
        )


def _seed_py(ws: Path, with_test: bool = True) -> None:
    fn_dir = ws / "n8n-functions" / "py"
    fn_dir.mkdir(parents=True)
    (fn_dir / "calculate_stats_by_category.py").write_text(CALC_STATS_PY_OK)
    if with_test:
        (ws / "n8n-functions-tests").mkdir()
        (ws / "n8n-functions-tests" / "test_calculate_stats_by_category.py").write_text(
            "from calculate_stats_by_category import calculate_stats_by_category\n"
            "def test_noop():\n"
            "    assert calculate_stats_by_category([]) == {}\n"
        )


def test_clean_template_passes(tmp_path):
    """Placeholder + glue + file + trailer + test → 0 errors."""
    _seed_js(tmp_path)
    code = (
        "{{HYDRATE:js:n8n-functions/js/calculateStatsByCategory.js}}\n"
        "\n"
        "return { json: { stats: calculateStatsByCategory([]) } };\n"
    )
    text = _wrap({
        "name": "Code",
        "type": "n8n-nodes-base.code",
        "parameters": {"jsCode": code},
    })
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert valid, errors


def test_clean_python_template_passes(tmp_path):
    _seed_py(tmp_path)
    code = (
        "{{HYDRATE:py:n8n-functions/py/calculate_stats_by_category.py}}\n"
        "\n"
        'return [{"json": {"stats": calculate_stats_by_category([])}}]\n'
    )
    text = _wrap({
        "name": "Code",
        "type": "n8n-nodes-base.code",
        "parameters": {"language": "python", "pythonCode": code},
    })
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert valid, errors


def test_deprecated_function_node_rejected(tmp_path):
    text = _wrap({
        "name": "Old",
        "type": "n8n-nodes-base.function",
        "parameters": {"functionCode": "return items;"},
    })
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert not valid
    assert any("function is deprecated" in e for e in errors), errors


def test_missing_placeholder_rejected(tmp_path):
    """Inlined JS (no {{HYDRATE:js:...}}) → error."""
    code = "const stats = {}; return { json: { stats } };"
    text = _wrap({
        "name": "Code",
        "type": "n8n-nodes-base.code",
        "parameters": {"jsCode": code},
    })
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert not valid
    assert any("HYDRATE:js" in e for e in errors), errors


def test_missing_placeholder_python_rejected(tmp_path):
    code = "return [{'json': {}}]"
    text = _wrap({
        "name": "Code",
        "type": "n8n-nodes-base.code",
        "parameters": {"language": "python", "pythonCode": code},
    })
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert not valid
    assert any("HYDRATE:py" in e for e in errors), errors


def test_missing_file_rejected(tmp_path):
    """Placeholder points to a file that doesn't exist on disk."""
    code = "{{HYDRATE:js:n8n-functions/js/missing.js}}\n"
    text = _wrap({
        "name": "Code",
        "type": "n8n-nodes-base.code",
        "parameters": {"jsCode": code},
    })
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert not valid
    assert any("not found" in e for e in errors), errors


def test_missing_trailer_rejected(tmp_path):
    """JS file lacks the conditional `if (typeof module !== \"undefined\")` trailer."""
    _seed_js(tmp_path, with_trailer=False)
    code = "{{HYDRATE:js:n8n-functions/js/calculateStatsByCategory.js}}\nreturn { json: {} };\n"
    text = _wrap({
        "name": "Code",
        "type": "n8n-nodes-base.code",
        "parameters": {"jsCode": code},
    })
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert not valid
    assert any("trailer" in e for e in errors), errors


def test_missing_test_rejected(tmp_path):
    """Function file exists with trailer, but no paired test file."""
    _seed_js(tmp_path, with_trailer=True, with_test=False)
    code = "{{HYDRATE:js:n8n-functions/js/calculateStatsByCategory.js}}\nreturn { json: {} };\n"
    text = _wrap({
        "name": "Code",
        "type": "n8n-nodes-base.code",
        "parameters": {"jsCode": code},
    })
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert not valid
    assert any("missing test file" in e for e in errors), errors


def test_missing_python_test_rejected(tmp_path):
    _seed_py(tmp_path, with_test=False)
    code = (
        "{{HYDRATE:py:n8n-functions/py/calculate_stats_by_category.py}}\n"
        'return [{"json": {}}]\n'
    )
    text = _wrap({
        "name": "Code",
        "type": "n8n-nodes-base.code",
        "parameters": {"language": "python", "pythonCode": code},
    })
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert not valid
    assert any("missing test file" in e for e in errors), errors


def test_empty_jscode_rejected(tmp_path):
    text = _wrap({
        "name": "Code",
        "type": "n8n-nodes-base.code",
        "parameters": {"jsCode": ""},
    })
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert not valid
    assert any("empty or missing" in e for e in errors), errors


def test_built_skips_code_discipline(tmp_path):
    """Source='built' must NOT run Code-node discipline checks (placeholders are already replaced)."""
    code = "const stats = {}; return { json: { stats } };"
    text = _wrap({
        "name": "Code",
        "type": "n8n-nodes-base.code",
        "parameters": {"jsCode": code},
    })
    valid, errors = validate_workflow_json(text, source="built", workspace=tmp_path)
    assert valid, errors


def test_workspace_none_skips_filesystem_checks(tmp_path):
    """Without a workspace, only the placeholder presence check runs (no file existence / trailer / test)."""
    code = "{{HYDRATE:js:n8n-functions/js/anywhere.js}}\nreturn { json: {} };\n"
    text = _wrap({
        "name": "Code",
        "type": "n8n-nodes-base.code",
        "parameters": {"jsCode": code},
    })
    valid, errors = validate_workflow_json(text, source="template", workspace=None)
    assert valid, errors


def test_non_code_nodes_skipped(tmp_path):
    """Non-Code nodes must not trigger any discipline checks."""
    text = _wrap({
        "name": "Webhook",
        "type": "n8n-nodes-base.webhook",
        "parameters": {"path": "smoke"},
    })
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert valid, errors
