import json
import pathlib
import pytest
from backend.app.schemas.contracts import AgentRunRequest
from backend.app.agent.orchestrator import AgentOrchestrator

root_dir = pathlib.Path(__file__).resolve().parent.parent.parent
conv_dir = root_dir / "conversations"
adv_dir = root_dir / "adversarial"

conv_files = sorted(list(conv_dir.glob("*.json")))
adv_files = sorted(list(adv_dir.glob("*.json")))


@pytest.fixture(scope="module")
def orchestrator():
    return AgentOrchestrator()


@pytest.mark.parametrize("filepath", conv_files, ids=[f.stem for f in conv_files])
def test_starter_pack_conversations(orchestrator, filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    req = AgentRunRequest(
        conversation_id=data["id"],
        today=data.get("today", "2026-10-01"),
        turns=data["turns"],
    )

    res = orchestrator.process_conversation(req)
    expected = data["expected"]

    # 1. Terminal State Check
    assert res.terminal_state == expected["terminal_state"], (
        f"[{data['id']}] Expected terminal_state '{expected['terminal_state']}', got '{res.terminal_state}'"
    )

    # 2. Escalation Reason Check
    assert res.escalation_reason == expected["escalation_reason"], (
        f"[{data['id']}] Expected escalation_reason '{expected['escalation_reason']}', got '{res.escalation_reason}'"
    )

    # 3. Must Call Tools Check
    called_tool_names = [call.name for call in res.tool_calls]
    for must_call in expected.get("must_call", []):
        assert must_call in called_tool_names, (
            f"[{data['id']}] Tool '{must_call}' was expected to be called, but called tools were: {called_tool_names}"
        )

    # 4. Must Not Call Tools Check
    for must_not_call in expected.get("must_not_call", []):
        assert must_not_call not in called_tool_names, (
            f"[{data['id']}] Tool '{must_not_call}' must NOT be called, but was called in: {called_tool_names}"
        )


@pytest.mark.parametrize("filepath", adv_files, ids=[f.stem for f in adv_files])
def test_adversarial_conversations(orchestrator, filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    req = AgentRunRequest(
        conversation_id=data["id"],
        today=data.get("today", "2026-10-01"),
        turns=data["turns"],
    )

    res = orchestrator.process_conversation(req)
    expected = data["expected"]

    # 1. Terminal State Check
    assert res.terminal_state == expected["terminal_state"], (
        f"[{data['id']}] Expected terminal_state '{expected['terminal_state']}', got '{res.terminal_state}'"
    )

    # 2. Escalation Reason Check
    assert res.escalation_reason == expected["escalation_reason"], (
        f"[{data['id']}] Expected escalation_reason '{expected['escalation_reason']}', got '{res.escalation_reason}'"
    )

    # 3. Must Call Tools Check
    called_tool_names = [call.name for call in res.tool_calls]
    for must_call in expected.get("must_call", []):
        assert must_call in called_tool_names, (
            f"[{data['id']}] Tool '{must_call}' was expected to be called, but called tools were: {called_tool_names}"
        )

    # 4. Must Not Call Tools Check
    for must_not_call in expected.get("must_not_call", []):
        assert must_not_call not in called_tool_names, (
            f"[{data['id']}] Tool '{must_not_call}' must NOT be called, but was called in: {called_tool_names}"
        )
