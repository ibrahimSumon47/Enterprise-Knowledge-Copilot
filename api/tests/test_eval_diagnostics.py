"""The evaluation's join from an answer to its admin-only refusal trace."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("run_eval", ROOT / "eval" / "run_eval.py")
assert SPEC and SPEC.loader
run_eval = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_eval)


def test_diagnostics_are_indexed_by_message_id() -> None:
    entries = [
        {
            "action": "chat.question",
            "detail": {
                "message_id": "message-1",
                "reason": "no quote verified against a retrieved passage",
                "raw_reply": '{"answer": "Receipts are due [1].", "evidence": []}',
                "provider_trace": ["verification: refused"],
            },
        },
        {"action": "chat.question", "detail": {"reason": "missing id"}},
        {"action": "document.upload", "detail": {"message_id": "ignored"}},
    ]
    found = run_eval.diagnostics_by_message(entries)
    assert found == {
        "message-1": {
            "reason": "no quote verified against a retrieved passage",
            "raw_reply": '{"answer": "Receipts are due [1].", "evidence": []}',
            "provider_trace": ["verification: refused"],
        }
    }


def test_diagnostics_parse_jsonb_returned_as_text() -> None:
    entries = [
        {
            "action": "chat.question",
            "detail": '{"message_id": "message-2", "reason": "empty evidence", "raw_reply": "{}"}',
        }
    ]
    found = run_eval.diagnostics_by_message(entries)
    assert found["message-2"]["reason"] == "empty evidence"
    assert found["message-2"]["raw_reply"] == "{}"


def test_retrieval_rank_soft_fails_when_the_admin_endpoint_is_down(monkeypatch) -> None:
    from types import SimpleNamespace

    def broken(*args, **kwargs):
        raise OSError("502")

    monkeypatch.setattr(run_eval, "http_json", broken)
    monkeypatch.setattr(run_eval.time, "sleep", lambda seconds: None)
    rank = run_eval.retrieval_rank(
        SimpleNamespace(api_url="https://example.test"),
        "question",
        "employee",
        "token",
        ["keyword"],
    )
    assert rank is None


def test_diagnostics_ignore_non_object_details() -> None:
    assert run_eval.diagnostics_by_message(
        [{"action": "chat.question", "detail": ["not", "an", "object"]}]
    ) == {}
    assert run_eval.diagnostics_by_message(
        [{"action": "chat.question", "detail": "not json"}]
    ) == {}
