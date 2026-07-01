"""
Faza 11 tests: FlowEngine branching, loop guard, ActionExecutor built-ins.

NOTE: this file previously imported `worker.services.flow_engine.Flow` (a
SQLAlchemy ORM class that was never defined there) and used
`app.services.action_executor.Contact` (an import path from a different,
unrelated codebase) — none of it matched the real implementation, so the
whole module failed to even import. Rewritten against the actual
implementation: FlowEngine takes an asyncpg connection plus plain
nodes/edges lists (worker.services.flow_engine.FlowEngine), and
ActionExecutor takes a plain dict action + params and returns
{"status", "outputs", "error", ...} (worker.services.action_executor.
ActionExecutor) — see apps/worker/src/worker/services/flow_engine.py and
action_executor.py.

Run: pytest apps/api/tests/test_phase11.py -v
"""
import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

from worker.services.flow_engine import FlowEngine, FlowContext
from worker.services.action_executor import ActionExecutor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ctx(variables: dict | None = None, contact: dict | None = None) -> FlowContext:
    ctx = FlowContext(
        conversation_id=str(uuid4()),
        contact=contact or {"name": "Ali"},
        tenant_id=str(uuid4()),
    )
    if variables:
        ctx.variables.update(variables)
    return ctx


@pytest.fixture
def conn():
    """A bare AsyncMock conn — only exercised by the 'action' node tests,
    which set conn.fetchrow explicitly."""
    return AsyncMock()


# ---------------------------------------------------------------------------
# FlowEngine tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_simple_message_flow(conn):
    """Trigger -> Message -> End sends one interpolated message."""
    nodes = [
        {"id": "n1", "type": "trigger", "data": {}},
        {"id": "n2", "type": "message", "data": {"text": "Salom {{contact.name}}!"}},
        {"id": "n3", "type": "end", "data": {}},
    ]
    edges = [
        {"id": "e1", "source": "n1", "target": "n2"},
        {"id": "e2", "source": "n2", "target": "n3"},
    ]
    ctx = make_ctx()
    messages = await FlowEngine(conn).run(nodes=nodes, edges=edges, ctx=ctx)
    assert messages == ["Salom Ali!"]


@pytest.mark.asyncio
async def test_multi_message_flow(conn):
    """Two consecutive message nodes both fire."""
    nodes = [
        {"id": "n1", "type": "trigger", "data": {}},
        {"id": "n2", "type": "message", "data": {"text": "Xush kelibsiz!"}},
        {"id": "n3", "type": "message", "data": {"text": "Sizga qanday yordam bera olaman?"}},
        {"id": "n4", "type": "end", "data": {}},
    ]
    edges = [
        {"id": "e1", "source": "n1", "target": "n2"},
        {"id": "e2", "source": "n2", "target": "n3"},
        {"id": "e3", "source": "n3", "target": "n4"},
    ]
    ctx = make_ctx()
    messages = await FlowEngine(conn).run(nodes=nodes, edges=edges, ctx=ctx)
    assert len(messages) == 2
    assert messages[0] == "Xush kelibsiz!"
    assert messages[1] == "Sizga qanday yordam bera olaman?"


@pytest.mark.asyncio
async def test_condition_true_branch(conn):
    """Condition node follows 'true' edge when condition is satisfied."""
    nodes = [
        {"id": "n1", "type": "trigger", "data": {}},
        {"id": "n2", "type": "condition", "data": {
            "variable": "score", "operator": "gt", "value": "5"
        }},
        {"id": "n3", "type": "message", "data": {"text": "Yuqori ball!"}},
        {"id": "n4", "type": "message", "data": {"text": "Past ball."}},
        {"id": "n5", "type": "end", "data": {}},
    ]
    edges = [
        {"id": "e1", "source": "n1", "target": "n2"},
        {"id": "e2", "source": "n2", "target": "n3", "label": "true"},
        {"id": "e3", "source": "n2", "target": "n4", "label": "false"},
        {"id": "e4", "source": "n3", "target": "n5"},
        {"id": "e5", "source": "n4", "target": "n5"},
    ]
    ctx = make_ctx(variables={"score": 8})
    messages = await FlowEngine(conn).run(nodes=nodes, edges=edges, ctx=ctx)
    assert messages == ["Yuqori ball!"]


@pytest.mark.asyncio
async def test_condition_false_branch(conn):
    """Condition node follows 'false' edge when condition is not satisfied."""
    nodes = [
        {"id": "n1", "type": "trigger", "data": {}},
        {"id": "n2", "type": "condition", "data": {
            "variable": "score", "operator": "gt", "value": "5"
        }},
        {"id": "n3", "type": "message", "data": {"text": "Yuqori ball!"}},
        {"id": "n4", "type": "message", "data": {"text": "Past ball."}},
        {"id": "n5", "type": "end", "data": {}},
    ]
    edges = [
        {"id": "e1", "source": "n1", "target": "n2"},
        {"id": "e2", "source": "n2", "target": "n3", "label": "true"},
        {"id": "e3", "source": "n2", "target": "n4", "label": "false"},
        {"id": "e4", "source": "n3", "target": "n5"},
        {"id": "e5", "source": "n4", "target": "n5"},
    ]
    ctx = make_ctx(variables={"score": 2})
    messages = await FlowEngine(conn).run(nodes=nodes, edges=edges, ctx=ctx)
    assert messages == ["Past ball."]


@pytest.mark.asyncio
async def test_condition_contains_operator(conn):
    nodes = [
        {"id": "n1", "type": "trigger", "data": {}},
        {"id": "n2", "type": "condition", "data": {
            "variable": "status", "operator": "contains", "value": "deliver"
        }},
        {"id": "n3", "type": "message", "data": {"text": "Yetkazilmoqda!"}},
        {"id": "n4", "type": "end", "data": {}},
    ]
    edges = [
        {"id": "e1", "source": "n1", "target": "n2"},
        {"id": "e2", "source": "n2", "target": "n3", "label": "true"},
        {"id": "e3", "source": "n3", "target": "n4"},
    ]
    ctx = make_ctx(variables={"status": "out_for_delivery"})
    messages = await FlowEngine(conn).run(nodes=nodes, edges=edges, ctx=ctx)
    assert messages == ["Yetkazilmoqda!"]


@pytest.mark.asyncio
async def test_variable_interpolation(conn):
    """Messages interpolate both contact.* and plain variables."""
    nodes = [
        {"id": "n1", "type": "trigger", "data": {}},
        {"id": "n2", "type": "message", "data": {
            "text": "{{contact.name}}, buyurtmangiz: {{order_id}}"
        }},
        {"id": "n3", "type": "end", "data": {}},
    ]
    edges = [
        {"id": "e1", "source": "n1", "target": "n2"},
        {"id": "e2", "source": "n2", "target": "n3"},
    ]
    ctx = make_ctx(
        variables={"order_id": "ORD-999"},
        contact={"name": "Sardor"},
    )
    messages = await FlowEngine(conn).run(nodes=nodes, edges=edges, ctx=ctx)
    assert messages == ["Sardor, buyurtmangiz: ORD-999"]


@pytest.mark.asyncio
async def test_infinite_loop_guard(conn):
    """Engine stops after 20 steps even if there's no end node."""
    nodes = [{"id": "n1", "type": "trigger", "data": {}}]
    edges = []
    for i in range(2, 30):
        nodes.append({"id": f"n{i}", "type": "message", "data": {"text": f"msg{i}"}})
    for i in range(1, 29):
        edges.append({"id": f"e{i}", "source": f"n{i}", "target": f"n{i + 1}"})

    ctx = make_ctx()
    messages = await FlowEngine(conn).run(nodes=nodes, edges=edges, ctx=ctx)
    assert len(messages) <= 20


@pytest.mark.asyncio
async def test_empty_flow_returns_no_messages(conn):
    """A flow with no nodes returns an empty list."""
    ctx = make_ctx()
    messages = await FlowEngine(conn).run(nodes=[], edges=[], ctx=ctx)
    assert messages == []


@pytest.mark.asyncio
async def test_action_node_runs_builtin_via_action_executor(conn):
    """An 'action' node looks the action up by name (tenant_actions row,
    asyncpg fetchrow) and runs it through the real ActionExecutor; the
    result is stashed in ctx.variables under '<action_name>_result'."""
    conn.fetchrow = AsyncMock(return_value={
        "name": "order_status",
        "display_name": "Order status",
        "description": "Look up an order",
        "params_schema": {},
        "action_type": "builtin",
        "webhook_url": None,
        "webhook_secret": None,
    })
    nodes = [
        {"id": "n1", "type": "trigger", "data": {}},
        {"id": "n2", "type": "action", "data": {
            "action_name": "order_status", "params": {"order_id": "ORD-123"}
        }},
        {"id": "n3", "type": "end", "data": {}},
    ]
    edges = [
        {"id": "e1", "source": "n1", "target": "n2"},
        {"id": "e2", "source": "n2", "target": "n3"},
    ]
    ctx = make_ctx()
    await FlowEngine(conn).run(nodes=nodes, edges=edges, ctx=ctx)

    result = ctx.variables["order_status_result"]
    assert result["status"] == "success"
    assert result["outputs"]["order_id"] == "ORD-123"


@pytest.mark.asyncio
async def test_action_node_missing_action_records_error(conn):
    """If tenant_actions has no matching row, the node stashes an
    {'error': ...} result instead of raising."""
    conn.fetchrow = AsyncMock(return_value=None)
    nodes = [
        {"id": "n1", "type": "trigger", "data": {}},
        {"id": "n2", "type": "action", "data": {"action_name": "nonexistent", "params": {}}},
        {"id": "n3", "type": "end", "data": {}},
    ]
    edges = [
        {"id": "e1", "source": "n1", "target": "n2"},
        {"id": "e2", "source": "n2", "target": "n3"},
    ]
    ctx = make_ctx()
    await FlowEngine(conn).run(nodes=nodes, edges=edges, ctx=ctx)
    assert "error" in ctx.variables["nonexistent_result"]


# ---------------------------------------------------------------------------
# ActionExecutor tests (real dict-based contract — see action_executor.py)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_builtin_collect_lead():
    action = {
        "name": "collect_lead",
        "action_type": "builtin",
        "webhook_url": None,
        "webhook_secret": None,
    }
    executor = ActionExecutor()
    result = await executor.execute(action, {"name": "Sardor", "phone": "+998901234567"})

    assert result["status"] == "success"
    assert result["outputs"]["name"] == "Sardor"
    assert result["outputs"]["phone"] == "+998901234567"


@pytest.mark.asyncio
async def test_builtin_order_status():
    action = {
        "name": "order_status",
        "action_type": "builtin",
        "webhook_url": None,
        "webhook_secret": None,
    }
    executor = ActionExecutor()
    result = await executor.execute(action, {"order_id": "ORD-123"})

    assert result["status"] == "success"
    assert result["outputs"]["order_id"] == "ORD-123"


@pytest.mark.asyncio
async def test_action_executor_records_error_for_unknown_builtin():
    action = {
        "name": "nonexistent_builtin",
        "action_type": "builtin",
        "webhook_url": None,
        "webhook_secret": None,
    }
    executor = ActionExecutor()
    result = await executor.execute(action, {})

    assert result["status"] == "error"
    assert result["error"] is not None
    assert result["outputs"] == {}


@pytest.mark.asyncio
async def test_builtin_book_appointment():
    action = {
        "name": "book_appointment",
        "action_type": "builtin",
        "webhook_url": None,
        "webhook_secret": None,
    }
    executor = ActionExecutor()
    result = await executor.execute(
        action, {"name": "Dilnoza", "phone": "+998901112233", "date": "2025-03-15"}
    )

    assert result["status"] == "success"
    assert result["outputs"]["status"] == "pending"
    assert result["outputs"]["data"]["name"] == "Dilnoza"
