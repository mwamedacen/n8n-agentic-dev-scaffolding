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
        "{{@:js:n8n-functions/js/calculateStatsByCategory.js}}\n"
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
        "{{@:py:n8n-functions/py/calculate_stats_by_category.py}}\n"
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
    """Inlined JS (no {{@:js:...}}) → error."""
    code = "const stats = {}; return { json: { stats } };"
    text = _wrap({
        "name": "Code",
        "type": "n8n-nodes-base.code",
        "parameters": {"jsCode": code},
    })
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert not valid
    assert any("@:js" in e for e in errors), errors


def test_missing_placeholder_python_rejected(tmp_path):
    code = "return [{'json': {}}]"
    text = _wrap({
        "name": "Code",
        "type": "n8n-nodes-base.code",
        "parameters": {"language": "python", "pythonCode": code},
    })
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert not valid
    assert any("@:py" in e for e in errors), errors


def test_missing_file_rejected(tmp_path):
    """Placeholder points to a file that doesn't exist on disk."""
    code = "{{@:js:n8n-functions/js/missing.js}}\n"
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
    code = "{{@:js:n8n-functions/js/calculateStatsByCategory.js}}\nreturn { json: {} };\n"
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
    code = "{{@:js:n8n-functions/js/calculateStatsByCategory.js}}\nreturn { json: {} };\n"
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
        "{{@:py:n8n-functions/py/calculate_stats_by_category.py}}\n"
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
    code = "{{@:js:n8n-functions/js/anywhere.js}}\nreturn { json: {} };\n"
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


# ---------- B-6: structural pure-function check ----------

def _write_js_fn(ws: Path, content: str, stem: str = "calculateStatsByCategory") -> str:
    fn_dir = ws / "n8n-functions" / "js"
    fn_dir.mkdir(parents=True, exist_ok=True)
    (fn_dir / f"{stem}.js").write_text(content)
    (ws / "n8n-functions-tests").mkdir(exist_ok=True)
    (ws / "n8n-functions-tests" / f"{stem}.test.js").write_text(
        f'const x = require("../n8n-functions/js/{stem}.js");\n'
    )
    code = (
        f"{{{{@:js:n8n-functions/js/{stem}.js}}}}\n"
        "\n"
        "return { json: {} };\n"
    )
    return _wrap({
        "name": "Code",
        "type": "n8n-nodes-base.code",
        "parameters": {"jsCode": code},
    })


def _write_py_fn(ws: Path, content: str, stem: str = "calculate_stats_by_category") -> str:
    fn_dir = ws / "n8n-functions" / "py"
    fn_dir.mkdir(parents=True, exist_ok=True)
    (fn_dir / f"{stem}.py").write_text(content)
    (ws / "n8n-functions-tests").mkdir(exist_ok=True)
    (ws / "n8n-functions-tests" / f"test_{stem}.py").write_text(
        f"from {stem} import {stem}\n"
        "def test_noop():\n"
        "    pass\n"
    )
    code = (
        f"{{{{@:py:n8n-functions/py/{stem}.py}}}}\n"
        "\n"
        'return [{"json": {}}]\n'
    )
    return _wrap({
        "name": "Code",
        "type": "n8n-nodes-base.code",
        "parameters": {"language": "python", "pythonCode": code},
    })


def test_js_function_only_passes(tmp_path):
    """A file with only `function foo() {...}` + trailer must pass."""
    text = _write_js_fn(
        tmp_path,
        'function foo() {\n  return 1;\n}\n'
        'if (typeof module !== "undefined") module.exports = { foo };\n',
        stem="foo",
    )
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert valid, errors


def test_js_top_level_const_rejected(tmp_path):
    """Top-level `const` outside a function is rejected."""
    text = _write_js_fn(
        tmp_path,
        'const x = 1;\n'
        'function foo() { return x; }\n'
        'if (typeof module !== "undefined") module.exports = { foo };\n',
        stem="foo",
    )
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert not valid
    assert any("top-level code" in e and "line 1" in e for e in errors), errors


def test_js_top_level_return_rejected(tmp_path):
    """The agent's aggregate_articles.js shape — top-level glue, no function — must fail."""
    text = _write_js_fn(
        tmp_path,
        'const articles = items[0].json.body || [];\n'
        'const stats = {};\n'
        'for (const a of articles) { stats[a.category] = (stats[a.category] || 0) + 1; }\n'
        'return [{ json: { stats } }];\n'
        'if (typeof module !== "undefined") module.exports = {};\n',
        stem="aggregate_articles",
    )
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert not valid
    # Should flag at least the first top-level non-function line.
    assert any("top-level code" in e for e in errors), errors


def test_js_top_level_for_loop_rejected(tmp_path):
    """A bare top-level for-loop (outside any function) is rejected."""
    text = _write_js_fn(
        tmp_path,
        'for (let i = 0; i < 3; i++) { console.log(i); }\n'
        'function foo() { return 1; }\n'
        'if (typeof module !== "undefined") module.exports = { foo };\n',
        stem="foo",
    )
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert not valid
    assert any("top-level code" in e and "line 1" in e for e in errors), errors


def test_js_multiple_functions_pass(tmp_path):
    """Two top-level `function` declarations are fine."""
    text = _write_js_fn(
        tmp_path,
        'function helperA() { return 1; }\n'
        'function helperB() { return helperA() + 1; }\n'
        'if (typeof module !== "undefined") module.exports = { helperA, helperB };\n',
        stem="helpers",
    )
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert valid, errors


def test_js_brace_inside_string_does_not_break_depth(tmp_path):
    """Curly braces inside string literals must not confuse the brace-depth tracker."""
    text = _write_js_fn(
        tmp_path,
        'function greet(name) {\n'
        '  const msg = "hello {" + name + "}";\n'
        '  return msg;\n'
        '}\n'
        'if (typeof module !== "undefined") module.exports = { greet };\n',
        stem="greet",
    )
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert valid, errors


def test_js_block_comment_is_stripped(tmp_path):
    """A multi-line /* */ comment ahead of a function must not register as top-level code."""
    text = _write_js_fn(
        tmp_path,
        '/**\n * JSDoc block.\n * @param {Array} xs\n */\n'
        'function foo(xs) { return xs.length; }\n'
        'if (typeof module !== "undefined") module.exports = { foo };\n',
        stem="foo",
    )
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert valid, errors


def test_py_def_only_passes(tmp_path):
    text = _write_py_fn(
        tmp_path,
        "def foo():\n"
        "    return 1\n",
        stem="foo",
    )
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert valid, errors


def test_py_top_level_assignment_rejected(tmp_path):
    text = _write_py_fn(
        tmp_path,
        "x = 1\n"
        "def foo():\n"
        "    return x\n",
        stem="foo",
    )
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert not valid
    assert any("top-level code" in e and "line 1" in e for e in errors), errors


def test_py_top_level_for_rejected(tmp_path):
    text = _write_py_fn(
        tmp_path,
        "for i in range(3):\n"
        "    print(i)\n"
        "def foo():\n"
        "    return 1\n",
        stem="foo",
    )
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert not valid
    assert any("top-level code" in e and "line 1" in e for e in errors), errors


def test_py_imports_and_comments_pass(tmp_path):
    text = _write_py_fn(
        tmp_path,
        "# A pure-function module.\n"
        "import json\n"
        "from typing import Any\n"
        "\n"
        "def foo(x: Any) -> str:\n"
        "    return json.dumps(x)\n",
        stem="foo",
    )
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert valid, errors


def test_py_module_docstring_single_line_passes(tmp_path):
    """A single-line module docstring is allowed (Python convention)."""
    text = _write_py_fn(
        tmp_path,
        '"""Pure aggregation."""\n'
        "\n"
        "def foo(x):\n"
        "    return x\n",
        stem="foo",
    )
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert valid, errors


def test_py_module_docstring_multiline_passes(tmp_path):
    """A multi-line module docstring is allowed."""
    text = _write_py_fn(
        tmp_path,
        '"""\n'
        "Multi-line\n"
        "module docstring.\n"
        '"""\n'
        "\n"
        "def foo(x):\n"
        "    return x\n",
        stem="foo",
    )
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert valid, errors


def test_py_string_after_def_still_rejected(tmp_path):
    """A bare top-level string AFTER a def is still a top-level expression, not a docstring."""
    text = _write_py_fn(
        tmp_path,
        "def foo(x):\n"
        "    return x\n"
        "\n"
        '"""bare string at top level"""\n',
        stem="foo",
    )
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert not valid
    assert any("top-level code" in e for e in errors), errors


def test_py_module_docstring_with_single_quotes_passes(tmp_path):
    """A `'''...'''` module docstring is also allowed."""
    text = _write_py_fn(
        tmp_path,
        "'''docstring'''\n"
        "\n"
        "def foo(x):\n"
        "    return x\n",
        stem="foo",
    )
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert valid, errors


def test_py_function_body_for_loop_passes(tmp_path):
    """A `for` inside a function body must NOT be flagged as top-level."""
    text = _write_py_fn(
        tmp_path,
        "def loop_sum(xs):\n"
        "    total = 0\n"
        "    for x in xs:\n"
        "        total += x\n"
        "    return total\n",
        stem="loop_sum",
    )
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert valid, errors
