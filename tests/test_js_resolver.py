"""Tests for helpers/placeholder/js_resolver.py."""
import json
from pathlib import Path

import pytest

from helpers.placeholder import js_resolver


CALC_STATS_JS = '''function calculateStatsByCategory(articles) {
  const stats = {};
  for (const article of articles) {
    const cat = article.category || "uncategorized";
    stats[cat] = (stats[cat] || 0) + 1;
  }
  return stats;
}
if (typeof module !== "undefined") module.exports = { calculateStatsByCategory };
'''


def _workflow_json(js_code: str) -> str:
    """Wrap a jsCode value into a minimal workflow JSON document."""
    return json.dumps(
        {
            "name": "Smoke",
            "nodes": [
                {
                    "name": "Code",
                    "type": "n8n-nodes-base.code",
                    "parameters": {"jsCode": js_code},
                }
            ],
            "connections": {},
            "settings": {},
        },
        indent=2,
    )


def test_multiline_js_with_quotes_produces_valid_json(tmp_path):
    """Multi-line JS containing quotes/backslashes/newlines must hydrate into valid JSON."""
    fn_dir = tmp_path / "n8n-functions" / "js"
    fn_dir.mkdir(parents=True)
    js_file = fn_dir / "calculateStatsByCategory.js"
    js_file.write_text(CALC_STATS_JS)

    raw = _workflow_json("{{@:js:n8n-functions/js/calculateStatsByCategory.js}}")
    out = js_resolver.resolve(raw, tmp_path)

    data = json.loads(out)
    code = data["nodes"][0]["parameters"]["jsCode"]
    assert "function calculateStatsByCategory" in code
    assert 'article.category || "uncategorized"' in code
    assert 'if (typeof module !== "undefined") module.exports' in code
    # Resolver writes `#` markers (preferred form).
    assert "/* #:js:n8n-functions/js/calculateStatsByCategory.js */" in code
    assert "/* /#:js:n8n-functions/js/calculateStatsByCategory.js */" in code


def test_canonical_INTERPOLATE_form_also_accepted(tmp_path):
    """Both `{{@:js:...}}` (alias) and `{{INTERPOLATE:js:...}}` (canonical) must hydrate."""
    fn_dir = tmp_path / "n8n-functions" / "js"
    fn_dir.mkdir(parents=True)
    (fn_dir / "calculateStatsByCategory.js").write_text(CALC_STATS_JS)

    raw = _workflow_json("{{INTERPOLATE:js:n8n-functions/js/calculateStatsByCategory.js}}")
    out = js_resolver.resolve(raw, tmp_path)
    data = json.loads(out)
    assert "function calculateStatsByCategory" in data["nodes"][0]["parameters"]["jsCode"]


def test_legacy_HYDRATE_form_no_longer_substitutes(tmp_path):
    """Hard cutover: `{{HYDRATE:js:...}}` is NOT recognized; the placeholder passes through unchanged."""
    fn_dir = tmp_path / "n8n-functions" / "js"
    fn_dir.mkdir(parents=True)
    (fn_dir / "calculateStatsByCategory.js").write_text(CALC_STATS_JS)

    raw = _workflow_json("{{HYDRATE:js:n8n-functions/js/calculateStatsByCategory.js}}")
    out = js_resolver.resolve(raw, tmp_path)
    data = json.loads(out)
    # Placeholder survives — resolver did not substitute. Residual validator catches this downstream.
    assert "{{HYDRATE:js:" in data["nodes"][0]["parameters"]["jsCode"]


def test_glue_survives_hydrate(tmp_path):
    """A jsCode field with a placeholder + n8n glue should keep the glue intact after hydrate."""
    fn_dir = tmp_path / "n8n-functions" / "js"
    fn_dir.mkdir(parents=True)
    (fn_dir / "calculateStatsByCategory.js").write_text(CALC_STATS_JS)

    glue = (
        "{{@:js:n8n-functions/js/calculateStatsByCategory.js}}\n"
        "\n"
        "const body = $input.body || {};\n"
        "const articles = Array.isArray(body.articles) ? body.articles : [];\n"
        "const stats = calculateStatsByCategory(articles);\n"
        "return { json: { stats } };\n"
    )
    raw = _workflow_json(glue)
    out = js_resolver.resolve(raw, tmp_path)

    data = json.loads(out)
    code = data["nodes"][0]["parameters"]["jsCode"]
    assert "const body = $input.body || {};" in code
    assert "const stats = calculateStatsByCategory(articles);" in code
    assert "return { json: { stats } };" in code


def test_round_trip_restores_placeholder_and_glue(tmp_path):
    """hydrate → dehydrate restores the @-form placeholder; glue is preserved verbatim."""
    fn_dir = tmp_path / "n8n-functions" / "js"
    fn_dir.mkdir(parents=True)
    (fn_dir / "calculateStatsByCategory.js").write_text(CALC_STATS_JS)

    glue = (
        "{{@:js:n8n-functions/js/calculateStatsByCategory.js}}\n"
        "\n"
        "const articles = $input.body.articles || [];\n"
        "return { json: { stats: calculateStatsByCategory(articles) } };\n"
    )
    raw = _workflow_json(glue)
    hydrated = js_resolver.resolve(raw, tmp_path)
    dehydrated = js_resolver.dehydrate(hydrated)

    data = json.loads(dehydrated)
    code = data["nodes"][0]["parameters"]["jsCode"]
    assert "{{@:js:n8n-functions/js/calculateStatsByCategory.js}}" in code
    assert "const articles = $input.body.articles || [];" in code
    assert "return { json: { stats: calculateStatsByCategory(articles) } };" in code
    assert "/* #:js:" not in code
    assert "/* DEHYDRATE:js:" not in code


def test_legacy_DEHYDRATE_marker_collapses_on_dehydrate(tmp_path):
    """A workflow with the old `/* DEHYDRATE:js:... */` markers (e.g. fetched from a deployed instance
    that was hydrated before this rename) must still collapse back to a `{{@:js:...}}` placeholder.
    """
    rel_path = "n8n-functions/js/calculateStatsByCategory.js"
    legacy_jscode = (
        f"/* DEHYDRATE:js:{rel_path} */\n"
        + CALC_STATS_JS.rstrip("\n") + "\n"
        + f"/* /DEHYDRATE:js:{rel_path} */\n"
        "\n"
        "return { json: {} };"
    )
    raw = _workflow_json(legacy_jscode)
    dehydrated = js_resolver.dehydrate(raw)
    code = json.loads(dehydrated)["nodes"][0]["parameters"]["jsCode"]
    assert "{{@:js:" + rel_path + "}}" in code
    assert "/* DEHYDRATE:js:" not in code


def test_canonical_MATCH_marker_collapses_on_dehydrate(tmp_path):
    """The canonical `/* MATCH:js:... */` form must also collapse on dehydrate."""
    rel_path = "n8n-functions/js/calculateStatsByCategory.js"
    match_jscode = (
        f"/* MATCH:js:{rel_path} */\n"
        + CALC_STATS_JS.rstrip("\n") + "\n"
        + f"/* /MATCH:js:{rel_path} */\n"
        "\n"
        "return { json: {} };"
    )
    raw = _workflow_json(match_jscode)
    dehydrated = js_resolver.dehydrate(raw)
    code = json.loads(dehydrated)["nodes"][0]["parameters"]["jsCode"]
    assert "{{@:js:" + rel_path + "}}" in code
    assert "/* MATCH:js:" not in code


def test_trailer_survives_injection(tmp_path):
    """The conditional `if (typeof module !== \"undefined\")` trailer must survive verbatim."""
    fn_dir = tmp_path / "n8n-functions" / "js"
    fn_dir.mkdir(parents=True)
    (fn_dir / "calculateStatsByCategory.js").write_text(CALC_STATS_JS)

    raw = _workflow_json("{{@:js:n8n-functions/js/calculateStatsByCategory.js}}")
    out = js_resolver.resolve(raw, tmp_path)

    data = json.loads(out)
    code = data["nodes"][0]["parameters"]["jsCode"]
    assert (
        'if (typeof module !== "undefined") module.exports = { calculateStatsByCategory };'
        in code
    )


def test_dehydrate_leaves_unrelated_strings_alone(tmp_path):
    """Strings that don't contain `#`/`MATCH`/`DEHYDRATE` markers must be left untouched."""
    raw = json.dumps(
        {
            "name": "Smoke",
            "nodes": [
                {
                    "name": "Set",
                    "type": "n8n-nodes-base.set",
                    "parameters": {"value": "hello /* not a marker */ world"},
                }
            ],
            "connections": {},
            "settings": {},
        },
        indent=2,
    )
    out = js_resolver.dehydrate(raw)
    data = json.loads(out)
    assert data["nodes"][0]["parameters"]["value"] == "hello /* not a marker */ world"


def test_resolve_rejects_absolute_paths(tmp_path):
    raw = _workflow_json("{{@:js:/abs/path.js}}")
    with pytest.raises(ValueError, match="Absolute paths"):
        js_resolver.resolve(raw, tmp_path)


def test_resolve_raises_on_missing_file(tmp_path):
    raw = _workflow_json("{{@:js:n8n-functions/js/missing.js}}")
    with pytest.raises(FileNotFoundError):
        js_resolver.resolve(raw, tmp_path)
