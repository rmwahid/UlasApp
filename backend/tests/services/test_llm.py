import pytest

from app.services.llm import LLMError, read_message


def test_read_message_returns_the_visible_answer():
    body = {"choices": [{"message": {"role": "assistant", "content": "  A watch.  "}}]}
    assert read_message(body) == "  A watch.  "


def test_read_message_reports_a_reasoning_only_answer():
    body = {
        "choices": [
            {
                "message": {"role": "assistant", "content": "", "reasoning_content": "thinking..."},
                "finish_reason": "length",
            }
        ]
    }
    with pytest.raises(LLMError) as error:
        read_message(body)
    assert "reasoning" in str(error.value)
    assert "length" in str(error.value)


def test_read_message_rejects_a_blank_answer():
    with pytest.raises(LLMError):
        read_message({"choices": [{"message": {"content": "   "}, "finish_reason": "stop"}]})


def test_read_message_rejects_an_answer_without_choices():
    with pytest.raises(LLMError):
        read_message({})
    with pytest.raises(LLMError):
        read_message({"choices": []})
