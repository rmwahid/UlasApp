import pytest

from app.services.llm_json import LLMOutputError, extract_json_object


def test_extract_json_object_reads_a_plain_object():
    assert extract_json_object('{"lines": []}') == {"lines": []}


def test_extract_json_object_ignores_prose_and_fences():
    answer = 'Sure! Here is the JSON:\n```json\n{"lines": [{"say": "halo"}]}\n```\nHope that helps.'
    assert extract_json_object(answer) == {"lines": [{"say": "halo"}]}


def test_extract_json_object_refuses_an_answer_without_an_object():
    with pytest.raises(LLMOutputError):
        extract_json_object("I could not decide.")


def test_extract_json_object_refuses_broken_json():
    with pytest.raises(LLMOutputError):
        extract_json_object('{"lines": [}')


def test_extract_json_object_refuses_a_json_array():
    with pytest.raises(LLMOutputError):
        extract_json_object("[1, 2, 3]")
