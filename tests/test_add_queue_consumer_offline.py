"""Offline tests for helpers/add_queue_consumer_to_workflow.py."""
import pytest

from helpers.add_queue_consumer_to_workflow import (
    _insert_consumer,
    _make_schedule_trigger_node,
    _parse_schedule_interval,
    _POP_NODE_NAME,
    _ACK_NODE_NAME,
    _IF_NODE_NAME,
    _SCHEDULE_NODE_NAME,
    _SCHEDULE_TRIGGER_TYPE,
)


def _minimal_template_no_trigger() -> dict:
    """No trigger at all — just a Set."""
    return {
        "name": "Smoke",
        "nodes": [
            {
                "id": "s1",
                "name": "Set",
                "type": "n8n-nodes-base.set",
                "typeVersion": 3.4,
                "position": [240, 300],
                "parameters": {},
            },
        ],
        "connections": {},
        "settings": {},
    }


def _minimal_template_webhook() -> dict:
    return {
        "name": "Smoke",
        "nodes": [
            {
                "id": "t1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [240, 300],
                "parameters": {"path": "smoke"},
            },
            {
                "id": "s1",
                "name": "Set",
                "type": "n8n-nodes-base.set",
                "typeVersion": 3.4,
                "position": [460, 300],
                "parameters": {},
            },
        ],
        "connections": {
            "Webhook": {"main": [[{"node": "Set", "type": "main", "index": 0}]]},
        },
        "settings": {},
    }


def _minimal_template_schedule() -> dict:
    return {
        "name": "Smoke",
        "nodes": [
            {
                "id": "t1",
                "name": "Schedule Trigger",
                "type": _SCHEDULE_TRIGGER_TYPE,
                "typeVersion": 1.3,
                "position": [240, 300],
                "parameters": {"rule": {"interval": [{"field": "minutes", "minutesInterval": 5}]}},
            },
            {
                "id": "s1",
                "name": "Set",
                "type": "n8n-nodes-base.set",
                "typeVersion": 3.4,
                "position": [460, 300],
                "parameters": {},
            },
        ],
        "connections": {
            "Schedule Trigger": {"main": [[{"node": "Set", "type": "main", "index": 0}]]},
        },
        "settings": {},
    }


def _kwargs(**override) -> dict:
    base = dict(
        stream_expr="={{ 'orders' }}",
        group_expr=None,
        consumer_expr=None,
        max_concurrency=1,
        max_retries=3,
        dlq_enabled=False,
        batch_size=1,
        claim_idle_ms=60000,
        schedule_interval="30s",
        ack_on_success_expression="={{ true }}",
        remove_existing_trigger=False,
    )
    base.update(override)
    return base


def test_no_trigger_inserts_schedule_trigger():
    tpl = _insert_consumer(_minimal_template_no_trigger(), **_kwargs())
    schedule = next(n for n in tpl["nodes"] if n["name"] == _SCHEDULE_NODE_NAME)
    assert schedule["type"] == _SCHEDULE_TRIGGER_TYPE
    assert schedule["typeVersion"] == 1.3


def test_existing_schedule_trigger_reused():
    tpl = _insert_consumer(_minimal_template_schedule(), **_kwargs())
    schedules = [n for n in tpl["nodes"] if n["type"] == _SCHEDULE_TRIGGER_TYPE]
    assert len(schedules) == 1, "should reuse existing schedule trigger, not duplicate"


def test_webhook_trigger_without_remove_flag_refused():
    with pytest.raises(SystemExit):
        _insert_consumer(_minimal_template_webhook(), **_kwargs(remove_existing_trigger=False))


def test_webhook_trigger_with_remove_flag_replaced():
    tpl = _insert_consumer(_minimal_template_webhook(), **_kwargs(remove_existing_trigger=True))
    names = [n["name"] for n in tpl["nodes"]]
    assert "Webhook" not in names
    assert _SCHEDULE_NODE_NAME in names


def test_pop_if_ack_nodes_present_in_order():
    tpl = _insert_consumer(_minimal_template_no_trigger(), **_kwargs())
    names = {n["name"] for n in tpl["nodes"]}
    assert _POP_NODE_NAME in names
    assert _IF_NODE_NAME in names
    assert _ACK_NODE_NAME in names


def test_ack_pulls_from_queue_pop_output():
    tpl = _insert_consumer(_minimal_template_no_trigger(), **_kwargs())
    ack = next(n for n in tpl["nodes"] if n["name"] == _ACK_NODE_NAME)
    inputs = ack["parameters"]["workflowInputs"]["value"]
    assert inputs["message_id"] == "={{ $('Queue Pop').first().json.message_id }}"
    assert inputs["stream"] == "={{ $('Queue Pop').first().json.stream }}"
    assert inputs["group"] == "={{ $('Queue Pop').first().json.group }}"


def test_default_ack_on_success_is_true():
    tpl = _insert_consumer(_minimal_template_no_trigger(), **_kwargs())
    ack = next(n for n in tpl["nodes"] if n["name"] == _ACK_NODE_NAME)
    inputs = ack["parameters"]["workflowInputs"]["value"]
    assert inputs["success"] == "={{ true }}"


def test_double_insert_refused():
    tpl = _insert_consumer(_minimal_template_no_trigger(), **_kwargs())
    with pytest.raises(SystemExit):
        _insert_consumer(tpl, **_kwargs())


def test_right_shift_existing_set_node():
    """Original Set at x=240 should shift right by 660 (Pop+If+Ack widths)."""
    tpl = _insert_consumer(_minimal_template_no_trigger(), **_kwargs())
    set_node = next(n for n in tpl["nodes"] if n["name"] == "Set")
    assert set_node["position"][0] == 240 + 660


def test_parse_schedule_interval_seconds():
    assert _parse_schedule_interval("30s") == {"field": "seconds", "secondsInterval": 30}


def test_parse_schedule_interval_minutes_default():
    assert _parse_schedule_interval("5") == {"field": "minutes", "minutesInterval": 5}


def test_parse_schedule_interval_hours():
    assert _parse_schedule_interval("2h") == {"field": "hours", "hoursInterval": 2}


def test_parse_schedule_interval_invalid():
    with pytest.raises(ValueError):
        _parse_schedule_interval("nonsense")


def test_make_schedule_trigger_node_shape():
    node = _make_schedule_trigger_node("Schedule Trigger", [240, 300], "30s")
    assert node["type"] == _SCHEDULE_TRIGGER_TYPE
    assert node["typeVersion"] == 1.3
    assert node["parameters"]["rule"]["interval"][0] == {
        "field": "seconds", "secondsInterval": 30,
    }


def test_pop_targets_correct_primitive():
    tpl = _insert_consumer(_minimal_template_no_trigger(), **_kwargs())
    pop = next(n for n in tpl["nodes"] if n["name"] == _POP_NODE_NAME)
    assert pop["parameters"]["workflowId"]["value"] == "{{@:env:workflows.queue_pop.id}}"


def test_ack_targets_correct_primitive():
    tpl = _insert_consumer(_minimal_template_no_trigger(), **_kwargs())
    ack = next(n for n in tpl["nodes"] if n["name"] == _ACK_NODE_NAME)
    assert ack["parameters"]["workflowId"]["value"] == "{{@:env:workflows.queue_ack.id}}"
