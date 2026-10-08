import asyncio

import pytest

from app.services import llm, matching
from app.services.llm_json import LLMOutputError


def _asset(
    asset_id="a01",
    kind="photo",
    width=1080,
    height=1920,
    duration=None,
    description="A watch on a wrist.",
):
    return {
        "id": asset_id,
        "kind": kind,
        "path": f"assets/{asset_id}.jpg",
        "name": asset_id,
        "width": width,
        "height": height,
        "duration": duration,
        "description": description,
    }


def _lines(count=2):
    return [
        {
            "id": f"L{index}",
            "section": "hook" if index == 1 else "proof",
            "text": f"line {index}",
            "hint": f"hint {index}",
        }
        for index in range(1, count + 1)
    ]


def test_orientation_reads_the_probe_dimensions():
    assert matching.orientation(_asset(width=1080, height=1920)) == "portrait"
    assert matching.orientation(_asset(width=1920, height=1080)) == "landscape"
    assert matching.orientation(_asset(width=800, height=800)) == "square"
    assert matching.orientation(_asset(width=0, height=0)) == "unknown"


def test_build_prompt_lists_material_facts_and_line_hints():
    assets = [_asset("a01"), _asset("a02", kind="clip", duration=12.5, width=1920, height=1080)]
    prompt = matching.build_prompt(_lines(2), assets)
    assert "a01 | photo | portrait | still | A watch on a wrist." in prompt
    assert "a02 | clip | landscape | 12.5s | A watch on a wrist." in prompt
    assert "L1 | hook | line 1 | hint: hint 1" in prompt
    assert "9:16" in prompt


def test_read_assignment_keeps_only_known_lines_and_assets():
    answer = (
        '{"assignment": [{"line": "L1", "asset": "a01"}, {"line": "L9", "asset": "a01"},'
        ' {"line": "L2", "asset": "a99"}, "nonsense", null], "notes": "  Because   it fits. "}'
    )
    assignment, notes = matching.read_assignment(answer, _lines(2), [_asset("a01")])
    assert assignment == {"L1": "a01"}
    assert notes == "Because it fits."


def test_read_assignment_accepts_a_fenced_answer():
    answer = 'Here you go:\n```json\n{"assignment": [{"line": "L1", "asset": "a01"}]}\n```'
    assignment, notes = matching.read_assignment(answer, _lines(1), [_asset("a01")])
    assert assignment == {"L1": "a01"}
    assert notes == ""


def test_read_assignment_refuses_an_answer_without_json():
    with pytest.raises(LLMOutputError):
        matching.read_assignment("I could not decide.", _lines(1), [_asset("a01")])


def _patch_answer(monkeypatch, answer: str) -> None:
    async def fake_complete(system, user):
        assert "a01 | photo" in user
        return answer

    monkeypatch.setattr(llm, "complete", fake_complete)


def test_assign_returns_a_complete_assignment(monkeypatch):
    _patch_answer(
        monkeypatch,
        '{"assignment": [{"line": "L1", "asset": "a01"}, {"line": "L2", "asset": "a02"}],'
        ' "notes": "watch leads"}',
    )
    assignment, notes, reason = asyncio.run(
        matching.assign(_lines(2), [_asset("a01"), _asset("a02")])
    )
    assert assignment == {"L1": "a01", "L2": "a02"}
    assert notes == "watch leads"
    assert reason == ""


def test_assign_reports_the_lines_the_model_left_out(monkeypatch):
    _patch_answer(monkeypatch, '{"assignment": [{"line": "L1", "asset": "a01"}]}')
    assignment, _, reason = asyncio.run(matching.assign(_lines(2), [_asset("a01"), _asset("a02")]))
    assert assignment == {"L1": "a01"}
    assert "automatic rotation" in reason


def test_assign_reports_material_that_had_no_description(monkeypatch):
    _patch_answer(
        monkeypatch,
        '{"assignment": [{"line": "L1", "asset": "a01"}, {"line": "L2", "asset": "a02"}]}',
    )
    assets = [_asset("a01"), _asset("a02", description=None)]
    assignment, _, reason = asyncio.run(matching.assign(_lines(2), assets))
    assert assignment == {"L1": "a01", "L2": "a02"}
    assert "no description" in reason


def test_assign_falls_back_when_nothing_is_described():
    assets = [_asset("a01", description=None)]
    assignment, notes, reason = asyncio.run(matching.assign(_lines(1), assets))
    assert assignment == {}
    assert notes == ""
    assert "no material has a description" in reason


def test_assign_falls_back_when_the_call_fails(monkeypatch):
    async def failing(system, user):
        raise llm.LLMError("connection refused")

    monkeypatch.setattr(llm, "complete", failing)
    assignment, _, reason = asyncio.run(matching.assign(_lines(1), [_asset("a01")]))
    assert assignment == {}
    assert "matching call failed" in reason


def test_assign_falls_back_when_the_answer_is_unusable(monkeypatch):
    _patch_answer(monkeypatch, "sure, I picked some footage for you")
    assignment, _, reason = asyncio.run(matching.assign(_lines(1), [_asset("a01")]))
    assert assignment == {}
    assert "unusable" in reason


def test_assign_does_nothing_without_lines_or_material():
    assert asyncio.run(matching.assign([], [_asset("a01")]))[2] == "nothing to place"
    assert asyncio.run(matching.assign(_lines(1), []))[2] == "nothing to place"
