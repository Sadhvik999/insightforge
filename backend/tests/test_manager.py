
import json
import pandas as pd
import pytest

from app.manager import run_manager, prepare_conversation_history


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

    # Verify conversation history is returned.
    history = result["conversation_history"]

    assert isinstance(history, list)

    # Previous user question should be preserved.
    assert any(
        message.get("role") == "user"
        for message in history
    )

    # Tool results should be preserved.
    assert any(
        message.get("role") == "tool"
        for message in history
    )

    # Final assistant response should be preserved.
    assert history[-1]["content"] == "Analysis completed."


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

    assert result["conversation_history"][-1]["content"] == (
        "No additional analysis is needed."
    )


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


def test_prepare_conversation_history():
    raw_history = [
        {"role": "user", "content": "What was the highest sales region?"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [make_tool_call("aggregate_data", {})]
        },
        {
            "role": "tool",
            "tool_name": "aggregate_data",
            "content": '{"success": true, "result": [{"Region": "West", "result": 900}]}'
        },
        {
            "role": "assistant",
            "content": "West had the highest sales at 900."
        }
    ]

    cleaned = prepare_conversation_history(raw_history)

    assert len(cleaned) == 4
    assert cleaned[0] == {
        "role": "user",
        "content": "What was the highest sales region?"
    }
    assert cleaned[1]["role"] == "assistant"
    assert cleaned[1]["tool_calls"] == [make_tool_call("aggregate_data", {})]
    assert cleaned[2]["role"] == "tool"
    assert "West" in cleaned[2]["content"]
    assert cleaned[3] == {
        "role": "assistant",
        "content": "West had the highest sales at 900."
    }


def test_prepare_conversation_history_sanitizes_plotly_figures():
    raw_history = [
        {"role": "user", "content": "Create a bar chart."},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [make_tool_call("visualize_data", {"chart_type": "bar"})]
        },
        {
            "role": "tool",
            "tool_name": "visualize_data",
            "content": json.dumps({
                "success": True,
                "result": {
                    "chart_type": "bar",
                    "x_column": "Region",
                    "y_column": "Sales",
                    "figure": {
                        "data": [{"x": ["East", "West"], "y": [100, 200]}],
                        "layout": {"title": "Sales by Region"}
                    }
                }
            })
        },
        {
            "role": "assistant",
            "content": "The bar chart has been created."
        }
    ]

    cleaned = prepare_conversation_history(raw_history)
    assert len(cleaned) == 4
    tool_msg = cleaned[2]
    assert tool_msg["role"] == "tool"
    assert "figure" not in tool_msg["content"]
    assert "chart_status" in tool_msg["content"]
    assert "bar" in tool_msg["content"]


def test_manager_zero_tool_response_triggers_retry(
    monkeypatch,
    sample_df
):
    responses = [
        make_message(content="I think Delhi had the highest sales."),
        make_message([make_tool_call("get_dataset_summary", {})]),
        make_message(content="Summary complete.")
    ]

    call_messages = []

    def fake_ask_manager(messages, tools):
        call_messages.append(messages.copy())
        return responses.pop(0)

    monkeypatch.setattr("app.manager.ask_manager", fake_ask_manager)

    tools = [{"type": "function", "function": {"name": "get_dataset_summary"}}]

    result = run_manager(
        sample_df,
        "Summarize the dataset.",
        tools,
        fake_executor
    )

    assert len(call_messages) == 3
    retry_prompt = call_messages[1][-1]
    assert retry_prompt["role"] == "user"
    assert "You have not executed any tool yet" in retry_prompt["content"]
    assert result["tool_calls_count"] == 1
    assert result["stop_reason"] == "completed"


def test_manager_zero_tool_retry_limit_enforced(
    monkeypatch,
    sample_df
):
    responses = [
        make_message(content="Text response 1."),
        make_message(content="Text response 2.")
    ]

    call_count = 0

    def fake_ask_manager(messages, tools):
        nonlocal call_count
        call_count += 1
        return responses.pop(0)

    monkeypatch.setattr("app.manager.ask_manager", fake_ask_manager)

    tools = [{"type": "function", "function": {"name": "get_dataset_summary"}}]

    result = run_manager(
        sample_df,
        "Summarize the dataset.",
        tools,
        fake_executor
    )

    assert call_count == 2
    assert result["tool_calls_count"] == 0
    assert result["tool_results"] == []
    assert result["stop_reason"] == "zero_tools_executed"
    assert "could not execute" in result["final_message"]


def test_manager_successful_retry_executes_tool(
    monkeypatch,
    sample_df
):
    responses = [
        make_message(content="Attempting text answer."),
        make_message([make_tool_call("get_column_info", {})]),
        make_message(content="Columns identified.")
    ]

    def fake_ask_manager(messages, tools):
        return responses.pop(0)

    monkeypatch.setattr("app.manager.ask_manager", fake_ask_manager)

    tools = [{"type": "function", "function": {"name": "get_column_info"}}]

    result = run_manager(
        sample_df,
        "List the columns.",
        tools,
        fake_executor
    )

    assert result["tool_calls_count"] == 1
    assert len(result["tool_results"]) == 1
    assert result["tool_results"][0]["tool"] == "get_column_info"
    assert result["stop_reason"] == "completed"


def test_followup_bar_to_scatter(
    monkeypatch,
    sample_df
):
    history = [
        {"role": "user", "content": "Create a bar chart showing Sales by City."},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [make_tool_call("visualize_data", {"chart_type": "bar", "x_column": "City", "y_column": "Sales"})]
        },
        {
            "role": "tool",
            "tool_name": "visualize_data",
            "content": json.dumps({"success": True, "result": {"chart_type": "bar", "chart_status": "created"}})
        },
        {"role": "assistant", "content": "The bar chart has been created."}
    ]

    sent_messages = []

    def fake_executor_viz(df, tool_call):
        return {"chart_type": tool_call["function"]["arguments"]["chart_type"], "figure": {"data": []}}

    def fake_ask_manager(messages, tools):
        sent_messages.append(messages.copy())
        if len(sent_messages) == 1:
            return make_message([
                make_tool_call("visualize_data", {"chart_type": "scatter", "x_column": "City", "y_column": "Sales"})
            ])
        return make_message(content="Scatter plot created.")

    monkeypatch.setattr("app.manager.ask_manager", fake_ask_manager)

    tools = [{"type": "function", "function": {"name": "visualize_data"}}]

    result = run_manager(
        sample_df,
        "Now create a scatter plot showing City versus Sales.",
        tools,
        fake_executor_viz,
        conversation_history=history
    )

    assert result["tool_calls_count"] == 1
    assert result["tool_results"][0]["arguments"]["chart_type"] == "scatter"
    assert any(m.get("role") == "tool" for m in sent_messages[0])


def test_followup_bar_to_line(
    monkeypatch,
    sample_df
):
    history = [
        {"role": "user", "content": "Create a bar chart showing Sales by City."},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [make_tool_call("visualize_data", {"chart_type": "bar", "x_column": "City", "y_column": "Sales"})]
        },
        {
            "role": "tool",
            "tool_name": "visualize_data",
            "content": json.dumps({"success": True, "result": {"chart_type": "bar", "chart_status": "created"}})
        },
        {"role": "assistant", "content": "The bar chart has been created."}
    ]

    def fake_executor_viz(df, tool_call):
        return {"chart_type": tool_call["function"]["arguments"]["chart_type"]}

    responses = [
        make_message([make_tool_call("visualize_data", {"chart_type": "line", "x_column": "City", "y_column": "Sales"})]),
        make_message(content="Line chart created.")
    ]

    def fake_ask_manager(messages, tools):
        return responses.pop(0)

    monkeypatch.setattr("app.manager.ask_manager", fake_ask_manager)

    tools = [{"type": "function", "function": {"name": "visualize_data"}}]

    result = run_manager(
        sample_df,
        "Now create a line chart showing Sales across City.",
        tools,
        fake_executor_viz,
        conversation_history=history
    )

    assert result["tool_calls_count"] == 1
    assert result["tool_results"][0]["arguments"]["chart_type"] == "line"


def test_followup_bar_to_histogram(
    monkeypatch,
    sample_df
):
    history = [
        {"role": "user", "content": "Create a bar chart showing Sales by City."},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [make_tool_call("visualize_data", {"chart_type": "bar", "x_column": "City", "y_column": "Sales"})]
        },
        {
            "role": "tool",
            "tool_name": "visualize_data",
            "content": json.dumps({"success": True, "result": {"chart_type": "bar"}})
        },
        {"role": "assistant", "content": "The bar chart has been created."}
    ]

    def fake_executor_viz(df, tool_call):
        return {"chart_type": tool_call["function"]["arguments"]["chart_type"]}

    responses = [
        make_message([make_tool_call("visualize_data", {"chart_type": "histogram", "x_column": "Sales"})]),
        make_message(content="Histogram created.")
    ]

    def fake_ask_manager(messages, tools):
        return responses.pop(0)

    monkeypatch.setattr("app.manager.ask_manager", fake_ask_manager)

    tools = [{"type": "function", "function": {"name": "visualize_data"}}]

    result = run_manager(
        sample_df,
        "Now create a histogram of Sales.",
        tools,
        fake_executor_viz,
        conversation_history=history
    )

    assert result["tool_calls_count"] == 1
    assert result["tool_results"][0]["arguments"]["chart_type"] == "histogram"


def test_followup_bar_to_numerical_analysis(
    monkeypatch,
    sample_df
):
    history = [
        {"role": "user", "content": "Create a bar chart showing Sales by City."},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [make_tool_call("visualize_data", {"chart_type": "bar", "x_column": "City", "y_column": "Sales"})]
        },
        {
            "role": "tool",
            "tool_name": "visualize_data",
            "content": json.dumps({"success": True, "result": {"chart_type": "bar"}})
        },
        {"role": "assistant", "content": "The bar chart has been created."}
    ]

    responses = [
        make_message([make_tool_call("get_dataset_summary", {})]),
        make_message(content="Summary complete.")
    ]

    def fake_ask_manager(messages, tools):
        return responses.pop(0)

    monkeypatch.setattr("app.manager.ask_manager", fake_ask_manager)

    tools = [{"type": "function", "function": {"name": "get_dataset_summary"}}]

    result = run_manager(
        sample_df,
        "What is the overall summary of this dataset?",
        tools,
        fake_executor,
        conversation_history=history
    )

    assert result["tool_calls_count"] == 1
    assert result["tool_results"][0]["tool"] == "get_dataset_summary"


def test_followup_analysis_to_visualization(
    monkeypatch,
    sample_df
):
    history = [
        {"role": "user", "content": "What are the columns?"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [make_tool_call("get_column_info", {})]
        },
        {
            "role": "tool",
            "tool_name": "get_column_info",
            "content": json.dumps({"columns": ["City", "Sales"]})
        },
        {"role": "assistant", "content": "The columns are City and Sales."}
    ]

    def fake_executor_viz(df, tool_call):
        return {"chart_type": tool_call["function"]["arguments"]["chart_type"]}

    responses = [
        make_message([make_tool_call("visualize_data", {"chart_type": "bar", "x_column": "City", "y_column": "Sales"})]),
        make_message(content="Bar chart created.")
    ]

    def fake_ask_manager(messages, tools):
        return responses.pop(0)

    monkeypatch.setattr("app.manager.ask_manager", fake_ask_manager)

    tools = [{"type": "function", "function": {"name": "visualize_data"}}]

    result = run_manager(
        sample_df,
        "Now create a bar chart of Sales by City.",
        tools,
        fake_executor_viz,
        conversation_history=history
    )

    assert result["tool_calls_count"] == 1
    assert result["tool_results"][0]["tool"] == "visualize_data"


def test_ordinary_conversational_response_does_not_retry(
    monkeypatch,
    sample_df
):
    call_count = 0

    def fake_ask_manager(messages, tools):
        nonlocal call_count
        call_count += 1
        return make_message(content="Hello! I am your AI data analyst. How can I help you today?")

    monkeypatch.setattr("app.manager.ask_manager", fake_ask_manager)

    tools = [{"type": "function", "function": {"name": "get_dataset_summary"}}]

    result = run_manager(
        sample_df,
        "Hello!",
        tools,
        fake_executor
    )

    assert call_count == 1
    assert result["tool_calls_count"] == 0
    assert result["stop_reason"] == "completed"
    assert "Hello!" in result["final_message"]


def test_manager_includes_conversation_history(
    monkeypatch,
    sample_df
):
    history = [
        {"role": "user", "content": "What was the highest sales region?"},
        {"role": "assistant", "content": "West had the highest sales at 900."}
    ]

    sent_messages = []

    def fake_ask_manager(messages, tools):
        sent_messages.extend(messages)
        return make_message(content="Follow-up answered.")

    monkeypatch.setattr(
        "app.manager.ask_manager",
        fake_ask_manager
    )

    result = run_manager(
        sample_df,
        "What was its profit?",
        [],
        fake_executor,
        conversation_history=history
    )

    assert result["final_message"] == "Follow-up answered."
    # The message history sent to ask_manager must contain the previous assistant message
    assert any(
        msg.get("role") == "assistant" and "West had the highest sales" in msg.get("content", "")
        for msg in sent_messages
    )
