"""Tests for the primitive-marker exemption in helpers/validate.py."""
import json

from helpers.validate import validate_workflow_json


def _wrap(node: dict) -> str:
    return json.dumps(
        {
            "name": "Smoke",
            "nodes": [node],
            "connections": {},
            "settings": {},
        },
        indent=2,
    )


def test_marker_first_line_passes(tmp_path):
    """Code node with the primitive marker as first line passes without errors."""
    code = (
        "// @n8n-harness:primitive — exempt from pure-function discipline\n"
        "const scope = $json.scope || 'default';\n"
        "await this.helpers.redis.call('SET', `lock-${scope}`, 'x', 'NX', 'EX', '60');\n"
        "return [{ json: { acquired: true } }];\n"
    )
    text = _wrap({
        "name": "Lock Acquire",
        "type": "n8n-nodes-base.code",
        "parameters": {"jsCode": code},
    })
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert valid, errors


def test_marker_with_leading_whitespace_passes(tmp_path):
    """Whitespace before the marker is tolerated by lstrip."""
    code = (
        "   \n"
        "// @n8n-harness:primitive\n"
        "const x = await this.helpers.redis.call('GET', 'foo');\n"
    )
    text = _wrap({
        "name": "Primitive",
        "type": "n8n-nodes-base.code",
        "parameters": {"jsCode": code},
    })
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert valid, errors


def test_no_marker_no_placeholder_rejected(tmp_path):
    """Without the marker, existing discipline (require placeholder) still applies."""
    code = "const stats = {}; return { json: { stats } };"
    text = _wrap({
        "name": "Code",
        "type": "n8n-nodes-base.code",
        "parameters": {"jsCode": code},
    })
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert not valid
    assert any("HYDRATE:js" in e for e in errors), errors


def test_function_node_still_rejected_unconditionally(tmp_path):
    """The deprecated `n8n-nodes-base.function` is rejected even if its code starts with the marker."""
    code = (
        "// @n8n-harness:primitive\n"
        "return items;\n"
    )
    text = _wrap({
        "name": "Old",
        "type": "n8n-nodes-base.function",
        "parameters": {"functionCode": code},
    })
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert not valid
    assert any("function is deprecated" in e for e in errors), errors


def test_built_with_marker_passes(tmp_path):
    """source='built' already bypasses Code-node discipline; marker is orthogonal but should still pass."""
    code = (
        "// @n8n-harness:primitive\n"
        "return [{ json: { ok: true } }];\n"
    )
    text = _wrap({
        "name": "Lock",
        "type": "n8n-nodes-base.code",
        "parameters": {"jsCode": code},
    })
    valid, errors = validate_workflow_json(text, source="built", workspace=tmp_path)
    assert valid, errors


def test_python_primitive_marker_passes(tmp_path):
    """The marker also exempts Python Code nodes (uses the same `// @n8n-harness:primitive` literal as the first stripped chars).
    Python code nodes don't typically use this marker since Python primitives aren't shipped, but the validator should still accept it.
    """
    code = (
        "// @n8n-harness:primitive\n"
        "return [{'json': {}}]\n"
    )
    text = _wrap({
        "name": "Code",
        "type": "n8n-nodes-base.code",
        "parameters": {"language": "python", "pythonCode": code},
    })
    valid, errors = validate_workflow_json(text, source="template", workspace=tmp_path)
    assert valid, errors
