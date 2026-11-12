
import pandas as pd
import pytest

from app.manager import run_manager


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "City": ["Delhi", "Mumbai", "Delhi"],
        "Sales": [500, 800, 700]
    })


def make_message(tool_calls=None, content=""):
    return {
        "role": "assistant",
        "content": content,
        "tool_calls": tool_calls or []
    }


def make_tool_call(name, arguments):
    return {
        "id": f"call_{name}",
        "function": {
            "name": name,
            "arguments": arguments
        }
    }


def fake_executor(df, tool_call):
    name = tool_call["function"]["name"]

    if name == "get_dataset_summary":
        return {"total_rows": len(df)}

    if name == "get_column_info":
        return {"columns": df.columns.tolist()}

    raise ValueError("Unknown tool")


def test_manager_executes_multiple_tools(
    monkeypatch,
    sample_df
):
    responses = [
        make_message([
            make_tool_call("get_dataset_summary", {})
        ]),
        make_message([
            make_tool_call("get_column_info", {})
        ]),
        make_message(content="Analysis completed.")
    ]

    call_history = []

    def fake_ask_manager(messages, tools):
        call_history.append(messages.copy())
        return responses.pop(0)

    monkeypatch.setattr(
        "app.manager.ask_manager",
        fake_ask_manager
    )

    result = run_manager(
        sample_df,
        "Summarize the dataset and inspect its columns.",
        [],
        fake_executor
    )

    assert result["tool_calls_count"] == 2
    assert len(result["tool_results"]) == 2
    assert result["stop_reason"] == "completed"
    assert result["final_message"] == "Analysis completed."

    assert result["tool_results"][0]["tool"] == (
        "get_dataset_summary"
    )

    assert result["tool_results"][1]["tool"] == (
        "get_column_info"
    )

    # Verify that the second Qwen request includes
    # the first tool's result.
    assert any(
        message["role"] == "tool"
        for message in call_history[1]
    )


def test_manager_stops_when_no_more_tools(
    monkeypatch,
    sample_df
):
    def fake_ask_manager(messages, tools):
        return make_message(
            content="No additional analysis is needed."
        )

    monkeypatch.setattr(
        "app.manager.ask_manager",
        fake_ask_manager
    )

    result = run_manager(
        sample_df,
        "Give me an overview.",
        [],
        fake_executor
    )

    assert result["tool_calls_count"] == 0
    assert result["tool_results"] == []
    assert result["final_message"] == (
        "No additional analysis is needed."
    )
    assert result["stop_reason"] == "completed"


def test_manager_respects_tool_call_limit(
    monkeypatch,
    sample_df
):
    calls = []

    def fake_ask_manager(messages, tools):
        return make_message([
            make_tool_call(
                "get_dataset_summary",
                {"attempt": len(calls)}
            )
        ])

    def fake_executor(df, tool_call):
        calls.append(tool_call)
        return {"success": True}

    monkeypatch.setattr(
        "app.manager.ask_manager",
        fake_ask_manager
    )

    result = run_manager(
        sample_df,
        "Perform analysis.",
        [],
        fake_executor,
        max_tool_calls=3
    )

    assert result["tool_calls_count"] == 3
    assert len(calls) == 3
    assert result["stop_reason"] == (
        "max_tool_calls_reached"
    )


def test_manager_rejects_duplicate_calls(
    monkeypatch,
    sample_df
):
    calls = []

    def fake_ask_manager(messages, tools):
        return make_message([
            make_tool_call(
                "get_dataset_summary",
                {}
            )
        ])

    def fake_executor(df, tool_call):
        calls.append(tool_call)
        return {"total_rows": len(df)}

    monkeypatch.setattr(
        "app.manager.ask_manager",
        fake_ask_manager
    )

    result = run_manager(
        sample_df,
        "Summarize the dataset.",
        [],
        fake_executor,
        max_tool_calls=3
    )

    assert len(calls) == 1
    assert len(result["tool_results"]) == 1
    assert result["tool_calls_count"] == 3
    assert result["stop_reason"] == (
        "max_tool_calls_reached"
    )


@pytest.mark.parametrize(
    "limit",
    [0, -1, 1.5, True, "5"]
)
def test_manager_rejects_invalid_tool_limit(
    sample_df,
    limit
):
    with pytest.raises(ValueError):
        run_manager(
            sample_df,
            "Test question",
            [],
            fake_executor,
            max_tool_calls=limit
        )
