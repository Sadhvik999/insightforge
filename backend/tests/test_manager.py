
import json
import pandas as pd
import pytest

from app.manager import (
    run_manager,
    prepare_conversation_history,
    is_visualization_query,
    is_compound_query,
    is_valid_visualization_result,
    has_valid_visualization,
    sanitize_tool_payload
)


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
        return {"chart_type": tool_call["function"]["arguments"]["chart_type"], "figure": {"data": [{"type": "scatter"}]}}

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
        return {"chart_type": tool_call["function"]["arguments"]["chart_type"], "figure": {"data": [{"type": "scatter"}]}}

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
        return {"chart_type": tool_call["function"]["arguments"]["chart_type"], "figure": {"data": [{"type": "scatter"}]}}

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
        return {"chart_type": tool_call["function"]["arguments"]["chart_type"], "figure": {"data": [{"type": "scatter"}]}}

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


def test_is_visualization_query():
    assert is_visualization_query("Create a bar chart showing average Profit for each Category.") is True
    assert is_visualization_query("Plot Sales versus Profit.") is True
    assert is_visualization_query("Draw a histogram of Sales.") is True
    assert is_visualization_query("Generate a line graph of Sales over Order Date.") is True
    assert is_visualization_query("Now show this as a bar chart.") is True
    assert is_visualization_query("Visualize Profit by Category.") is True
    assert is_visualization_query("Calculate average Profit by Category and create a bar chart.") is True
    assert is_visualization_query("What is the average profit for each category?") is False
    assert is_visualization_query("Calculate total sales by region.") is False
    assert is_visualization_query("Show total sales for each segment.") is False
    assert is_visualization_query("Draw conclusions from the data.") is False

    # Negation queries
    assert is_visualization_query("Don't create a chart; just calculate average profit") is False
    assert is_visualization_query("Do not plot anything") is False
    assert is_visualization_query("Without a chart, calculate total sales") is False
    assert is_visualization_query("No graph, just calculate average profit") is False
    assert is_visualization_query("Skip the chart and give me the numbers") is False
    assert is_visualization_query("Don't make a line plot, create a bar chart") is True

    # References to existing visualizations / explanations
    assert is_visualization_query("Explain the previous chart") is False
    assert is_visualization_query("Describe the plot above") is False
    assert is_visualization_query("What does the previous chart show?") is False
    assert is_visualization_query("Interpret the visualization") is False
    assert is_visualization_query("Summarize the previous graph") is False
    assert is_visualization_query("Tell me about this chart") is False
    assert is_visualization_query("Create a bar chart and explain it") is True
    assert is_visualization_query("Plot Sales vs Profit and describe it") is True

    # Ordinary statements about charts without creation intent
    assert is_visualization_query("The previous chart is confusing") is False
    assert is_visualization_query("I like this graph") is False
    assert is_visualization_query("The chart looks incorrect") is False
    assert is_visualization_query("The previous plot is confusing") is False
    assert is_visualization_query("The plot looks incorrect") is False
    assert is_visualization_query("I like this plot") is False
    assert is_visualization_query("This chart is useful") is False
    assert is_visualization_query("There is a bar chart") is False
    assert is_visualization_query("The graph has too many labels") is False

    # Instructional questions (explanations of how to visualize)
    assert is_visualization_query("Explain how to create a chart") is False
    assert is_visualization_query("How do I create a bar chart?") is False
    assert is_visualization_query("How can I make a plot?") is False
    assert is_visualization_query("How to visualize sales?") is False
    assert is_visualization_query("Show me how to create a chart") is False

    # Cross-clause prevention (creation verb in one clause, chart mention in another)
    assert is_visualization_query("Create a summary of the data, because the chart is broken") is False
    assert is_visualization_query("Generate statistics for sales, the graph is not needed") is False

    # Imperative "chart" and explicit creation intent
    assert is_visualization_query("Chart Sales by Category") is True
    assert is_visualization_query("Plot Sales by Category") is True
    assert is_visualization_query("Create a bar chart of Sales") is True
    assert is_visualization_query("Generate a histogram of Profit") is True
    assert is_visualization_query("Show Sales by Region as a bar chart") is True
    assert is_visualization_query("Don't create a chart; calculate average profit") is False
    assert is_visualization_query("Don't create a line plot, create a bar chart") is True


def test_barchart_with_sum_aggregation(monkeypatch, sample_df):
    tools = [
        {"type": "function", "function": {"name": "aggregate_data"}},
        {"type": "function", "function": {"name": "visualize_data"}}
    ]

    captured_tools = []

    def fake_ask_manager(messages, active_tools):
        captured_tools.append(active_tools)
        if len(captured_tools) == 1:
            return make_message([
                make_tool_call("visualize_data", {
                    "chart_type": "bar",
                    "x_column": "City",
                    "y_column": "Sales",
                    "aggregation": "sum"
                })
            ])
        return make_message(content="Bar chart created.")

    def fake_executor_viz(df, tool_call):
        args = tool_call["function"]["arguments"]
        return {"chart_type": args["chart_type"], "aggregation": args.get("aggregation", "sum"), "figure": {"data": [{"type": "bar"}]}}

    monkeypatch.setattr("app.manager.ask_manager", fake_ask_manager)

    result = run_manager(
        sample_df,
        "Create a bar chart showing total Sales for each City.",
        tools,
        fake_executor_viz
    )

    # Verify that only visualize_data was offered to the manager
    assert len(captured_tools[0]) == 1
    assert captured_tools[0][0]["function"]["name"] == "visualize_data"
    assert result["tool_calls_count"] == 1
    assert result["tool_results"][0]["tool"] == "visualize_data"
    assert result["tool_results"][0]["arguments"]["aggregation"] == "sum"
    assert result["stop_reason"] == "completed"


def test_barchart_with_mean_aggregation(monkeypatch, sample_df):
    tools = [
        {"type": "function", "function": {"name": "aggregate_data"}},
        {"type": "function", "function": {"name": "visualize_data"}}
    ]

    captured_tools = []

    def fake_ask_manager(messages, active_tools):
        captured_tools.append(active_tools)
        if len(captured_tools) == 1:
            return make_message([
                make_tool_call("visualize_data", {
                    "chart_type": "bar",
                    "x_column": "City",
                    "y_column": "Sales",
                    "aggregation": "mean"
                })
            ])
        return make_message(content="Bar chart with average created.")

    def fake_executor_viz(df, tool_call):
        args = tool_call["function"]["arguments"]
        return {"chart_type": args["chart_type"], "aggregation": args.get("aggregation"), "figure": {"data": [{"type": "bar"}]}}

    monkeypatch.setattr("app.manager.ask_manager", fake_ask_manager)

    result = run_manager(
        sample_df,
        "Create a bar chart showing average Profit for each Category.",
        tools,
        fake_executor_viz
    )

    # Active tools restricted to visualize_data
    assert len(captured_tools[0]) == 1
    assert captured_tools[0][0]["function"]["name"] == "visualize_data"
    assert result["tool_calls_count"] == 1
    assert result["tool_results"][0]["tool"] == "visualize_data"
    assert result["tool_results"][0]["arguments"]["aggregation"] == "mean"
    assert result["stop_reason"] == "completed"


def test_imperative_chart_prioritizes_visualize_data(monkeypatch, sample_df):
    tools = [
        {"type": "function", "function": {"name": "aggregate_data"}},
        {"type": "function", "function": {"name": "visualize_data"}}
    ]

    captured_tools = []

    def fake_ask_manager(messages, active_tools):
        captured_tools.append(active_tools)
        if len(captured_tools) == 1:
            return make_message([
                make_tool_call("visualize_data", {
                    "chart_type": "bar",
                    "x_column": "Category",
                    "y_column": "Sales"
                })
            ])
        return make_message(content="Sales by Category charted.")

    def fake_executor_viz(df, tool_call):
        args = tool_call["function"]["arguments"]
        return {"chart_type": args["chart_type"], "figure": {"data": [{"type": "bar"}]}}

    monkeypatch.setattr("app.manager.ask_manager", fake_ask_manager)

    result = run_manager(
        sample_df,
        "Chart Sales by Category.",
        tools,
        fake_executor_viz
    )

    # Active tools restricted to visualize_data for imperative "chart"
    assert len(captured_tools[0]) == 1
    assert captured_tools[0][0]["function"]["name"] == "visualize_data"
    assert result["tool_calls_count"] == 1
    assert result["tool_results"][0]["tool"] == "visualize_data"
    assert result["stop_reason"] == "completed"


def test_ordinary_aggregation_without_chart_request(monkeypatch, sample_df):
    tools = [
        {"type": "function", "function": {"name": "aggregate_data"}},
        {"type": "function", "function": {"name": "visualize_data"}}
    ]

    captured_tools = []

    def fake_ask_manager(messages, active_tools):
        captured_tools.append(active_tools)
        if len(captured_tools) == 1:
            return make_message([
                make_tool_call("aggregate_data", {
                    "group_column": "City",
                    "target_column": "Sales",
                    "operation": "mean"
                })
            ])
        return make_message(content="Mean sales calculated.")

    def fake_executor_agg(df, tool_call):
        return [{"City": "Delhi", "result": 600}]

    monkeypatch.setattr("app.manager.ask_manager", fake_ask_manager)

    result = run_manager(
        sample_df,
        "What is the average sales for each city?",
        tools,
        fake_executor_agg
    )

    # All tools remain available for ordinary numerical analysis
    assert len(captured_tools[0]) == 2
    assert result["tool_calls_count"] == 1
    assert result["tool_results"][0]["tool"] == "aggregate_data"
    assert result["tool_results"][0]["arguments"]["operation"] == "mean"
    assert result["stop_reason"] == "completed"


def test_visualization_followup_after_numerical_analysis(monkeypatch, sample_df):
    history = [
        {"role": "user", "content": "What is the total sales for each city?"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [make_tool_call("aggregate_data", {"group_column": "City", "target_column": "Sales", "operation": "sum"})]
        },
        {
            "role": "tool",
            "tool_name": "aggregate_data",
            "content": json.dumps([{"City": "Delhi", "Sales": 1200}, {"City": "Mumbai", "Sales": 800}])
        },
        {"role": "assistant", "content": "Total sales calculated."}
    ]

    tools = [
        {"type": "function", "function": {"name": "aggregate_data"}},
        {"type": "function", "function": {"name": "visualize_data"}}
    ]

    captured_tools = []

    def fake_ask_manager(messages, active_tools):
        captured_tools.append(active_tools)
        if len(captured_tools) == 1:
            return make_message([
                make_tool_call("visualize_data", {
                    "chart_type": "bar",
                    "x_column": "City",
                    "y_column": "Sales",
                    "aggregation": "sum"
                })
            ])
        return make_message(content="Bar chart created.")

    def fake_executor_viz(df, tool_call):
        return {"chart_type": "bar", "figure": {"data": [{"type": "bar"}]}}

    monkeypatch.setattr("app.manager.ask_manager", fake_ask_manager)

    result = run_manager(
        sample_df,
        "Now create a bar chart of Sales by City.",
        tools,
        fake_executor_viz,
        conversation_history=history
    )

    assert len(captured_tools[0]) == 1
    assert captured_tools[0][0]["function"]["name"] == "visualize_data"
    assert result["tool_calls_count"] == 1
    assert result["tool_results"][0]["tool"] == "visualize_data"


def test_no_false_success_message_when_visualization_fails(monkeypatch, sample_df):
    tools = [
        {"type": "function", "function": {"name": "visualize_data"}}
    ]

    responses = [
        make_message([
            make_tool_call("visualize_data", {
                "chart_type": "bar",
                "x_column": "InvalidCol",
                "y_column": "Sales"
            })
        ]),
        make_message(content="The bar chart has been created successfully.")
    ]

    def fake_ask_manager(messages, active_tools):
        return responses.pop(0)

    def fake_executor_fail(df, tool_call):
        raise ValueError("Column not found: InvalidCol")

    monkeypatch.setattr("app.manager.ask_manager", fake_ask_manager)

    result = run_manager(
        sample_df,
        "Create a bar chart showing Sales for each InvalidCol.",
        tools,
        fake_executor_fail
    )

    # Tool execution failed, so visualize_data did not succeed
    assert result["stop_reason"] == "visualization_failed"
    assert "could not be generated" in result["final_message"]
    assert "successfully" not in result["final_message"]
    # Verify that conversation_history does not contain the false claim
    last_assistant_msg = [m for m in result["conversation_history"] if m.get("role") == "assistant"][-1]
    assert "successfully" not in last_assistant_msg.get("content", "")
    assert "could not be generated" in last_assistant_msg.get("content", "")


def test_is_valid_visualization_result():
    # Valid non-empty figure with valid trace dicts
    assert is_valid_visualization_result({"chart_type": "bar", "figure": {"data": [{"type": "bar"}]}}) is True
    assert is_valid_visualization_result({"figure": {"data": [{"x": [1, 2], "y": [3, 4]}], "layout": {}}}) is True
    assert is_valid_visualization_result({"data": [{"type": "bar"}]}) is True
    assert is_valid_visualization_result({"figure": {"data": [{"type": "bar"}, {"type": "line"}]}}) is True

    # Empty data list rejected
    assert is_valid_visualization_result({"chart_type": "bar", "figure": {"data": []}}) is False
    assert is_valid_visualization_result({"data": []}) is False

    # Missing data or figure
    assert is_valid_visualization_result({"chart_type": "bar"}) is False
    assert is_valid_visualization_result({"figure": {"layout": {}}}) is False

    # Empty figure
    assert is_valid_visualization_result({"chart_type": "bar", "figure": {}}) is False

    # None figure
    assert is_valid_visualization_result({"chart_type": "bar", "figure": None}) is False

    # Malformed data (not a list, list with primitives, empty dict, or None)
    assert is_valid_visualization_result({"figure": {"data": "not a list"}}) is False
    assert is_valid_visualization_result({"figure": {"data": [1, 2]}}) is False
    assert is_valid_visualization_result({"figure": {"data": [None]}}) is False
    assert is_valid_visualization_result({"figure": {"data": [{}]}}) is False
    assert is_valid_visualization_result({"figure": {"data": [{"type": "bar"}, {}]}}) is False

    # Non-dictionary result
    assert is_valid_visualization_result("not a dict") is False
    assert is_valid_visualization_result([{"figure": {"data": [{"type": "bar"}]}}]) is False
    assert is_valid_visualization_result(None) is False


def test_visualization_validation_valid_figure(monkeypatch, sample_df):
    tools = [{"type": "function", "function": {"name": "visualize_data"}}]

    responses = [
        make_message([make_tool_call("visualize_data", {"chart_type": "bar", "x_column": "City", "y_column": "Sales"})]),
        make_message(content="Bar chart created successfully.")
    ]

    def fake_ask_manager(messages, active_tools):
        return responses.pop(0)

    def fake_executor(df, tool_call):
        return {
            "chart_type": "bar",
            "x_column": "City",
            "y_column": "Sales",
            "figure": {"data": [{"x": ["Delhi", "Mumbai"], "y": [500, 800]}], "layout": {"title": "Sales"}}
        }

    monkeypatch.setattr("app.manager.ask_manager", fake_ask_manager)

    result = run_manager(
        sample_df,
        "Create a bar chart showing Sales by City.",
        tools,
        fake_executor
    )

    assert result["stop_reason"] == "completed"
    assert len(result["tool_results"]) == 1
    assert result["tool_results"][0]["tool"] == "visualize_data"
    # Preserves valid figure for the frontend
    assert result["tool_results"][0]["results"]["figure"]["data"][0]["y"] == [500, 800]
    assert has_valid_visualization(result["tool_results"]) is True


def test_visualization_validation_missing_figure(monkeypatch, sample_df):
    tools = [{"type": "function", "function": {"name": "visualize_data"}}]

    responses = [
        make_message([make_tool_call("visualize_data", {"chart_type": "bar", "x_column": "City", "y_column": "Sales"})]),
        make_message(content="The chart has been created.")
    ]

    def fake_ask_manager(messages, active_tools):
        return responses.pop(0)

    def fake_executor_missing_figure(df, tool_call):
        # Missing 'figure' key
        return {
            "chart_type": "bar",
            "x_column": "City",
            "y_column": "Sales"
        }

    monkeypatch.setattr("app.manager.ask_manager", fake_ask_manager)

    result = run_manager(
        sample_df,
        "Create a bar chart showing Sales by City.",
        tools,
        fake_executor_missing_figure
    )

    assert result["stop_reason"] == "visualization_failed"
    assert result["final_message"] == "The requested visualization could not be generated."
    assert len(result["tool_results"]) == 0
    assert has_valid_visualization(result["tool_results"]) is False


def test_visualization_validation_empty_figure(monkeypatch, sample_df):
    tools = [{"type": "function", "function": {"name": "visualize_data"}}]

    responses = [
        make_message([make_tool_call("visualize_data", {"chart_type": "bar", "x_column": "City", "y_column": "Sales"})]),
        make_message(content="The chart has been created.")
    ]

    def fake_ask_manager(messages, active_tools):
        return responses.pop(0)

    def fake_executor_empty_figure(df, tool_call):
        # 'figure' is an empty dictionary
        return {
            "chart_type": "bar",
            "x_column": "City",
            "y_column": "Sales",
            "figure": {}
        }

    monkeypatch.setattr("app.manager.ask_manager", fake_ask_manager)

    result = run_manager(
        sample_df,
        "Create a bar chart showing Sales by City.",
        tools,
        fake_executor_empty_figure
    )

    assert result["stop_reason"] == "visualization_failed"
    assert result["final_message"] == "The requested visualization could not be generated."
    assert len(result["tool_results"]) == 0
    assert has_valid_visualization(result["tool_results"]) is False


def test_visualization_validation_executor_exception(monkeypatch, sample_df):
    tools = [{"type": "function", "function": {"name": "visualize_data"}}]

    responses = [
        make_message([make_tool_call("visualize_data", {"chart_type": "bar", "x_column": "City", "y_column": "Sales"})]),
        make_message(content="The chart was completed.")
    ]

    def fake_ask_manager(messages, active_tools):
        return responses.pop(0)

    def fake_executor_raises(df, tool_call):
        raise ValueError("Plotly figure generation crashed")

    monkeypatch.setattr("app.manager.ask_manager", fake_ask_manager)

    result = run_manager(
        sample_df,
        "Create a bar chart showing Sales by City.",
        tools,
        fake_executor_raises
    )

    assert result["stop_reason"] == "visualization_failed"
    assert result["final_message"] == "The requested visualization could not be generated."
    assert len(result["tool_results"]) == 0
    assert has_valid_visualization(result["tool_results"]) is False


def test_ordinary_aggregation_remains_unaffected_by_viz_validation(monkeypatch, sample_df):
    tools = [
        {"type": "function", "function": {"name": "aggregate_data"}},
        {"type": "function", "function": {"name": "visualize_data"}}
    ]

    responses = [
        make_message([make_tool_call("aggregate_data", {"group_column": "City", "target_column": "Sales", "operation": "mean"})]),
        make_message(content="The mean sales have been calculated.")
    ]

    def fake_ask_manager(messages, active_tools):
        return responses.pop(0)

    def fake_executor_agg(df, tool_call):
        # Aggregation result does not have a figure field
        return [{"City": "Delhi", "result": 600}]

    monkeypatch.setattr("app.manager.ask_manager", fake_ask_manager)

    result = run_manager(
        sample_df,
        "What is the average sales for each city?",
        tools,
        fake_executor_agg
    )

    assert result["stop_reason"] == "completed"
    assert len(result["tool_results"]) == 1
    assert result["tool_results"][0]["tool"] == "aggregate_data"
    assert result["tool_results"][0]["results"] == [{"City": "Delhi", "result": 600}]


# --------------------------------------------------
# SANITIZE TOOL PAYLOAD & FIGURE STRIPPING TESTS
# --------------------------------------------------

def test_sanitize_tool_payload_valid_direct_figure():
    payload = {
        "chart_type": "bar",
        "figure": {
            "data": [{"x": ["North", "South"], "y": [100, 200]}],
            "layout": {"title": "Sales by Region"}
        }
    }
    sanitized = sanitize_tool_payload(payload)
    data = json.loads(sanitized)

    assert "figure" not in data
    assert data["chart_status"] == "Visualization generated successfully."
    assert data["chart_type"] == "bar"
    assert '"figure":' not in sanitized


def test_sanitize_tool_payload_empty_direct_figure():
    payload = {
        "chart_type": "bar",
        "figure": {}
    }
    sanitized = sanitize_tool_payload(payload)
    data = json.loads(sanitized)

    assert "figure" not in data
    assert data["chart_status"] == "Visualization generation failed."
    assert data["chart_type"] == "bar"
    assert '"figure":' not in sanitized


def test_sanitize_tool_payload_missing_figure_no_false_success():
    payload = {
        "operation": "mean",
        "target_column": "Sales",
        "result": 123.45
    }
    sanitized = sanitize_tool_payload(payload)
    data = json.loads(sanitized)

    assert "figure" not in data
    assert "chart_status" not in data
    assert data["operation"] == "mean"
    assert data["result"] == 123.45


def test_sanitize_tool_payload_nested_valid_figure():
    payload = {
        "success": True,
        "result": {
            "chart_type": "scatter",
            "x_column": "Sales",
            "y_column": "Profit",
            "figure": {
                "data": [{"x": [10, 20], "y": [5, 15]}],
                "layout": {"title": "Sales vs Profit"}
            }
        }
    }
    sanitized = sanitize_tool_payload(payload)
    data = json.loads(sanitized)

    assert data["success"] is True
    assert "figure" not in data["result"]
    assert data["result"]["chart_status"] == "Visualization generated successfully."
    assert data["result"]["chart_type"] == "scatter"
    assert '"figure":' not in sanitized


def test_sanitize_tool_payload_nested_empty_figure():
    payload = {
        "success": False,
        "result": {
            "chart_type": "line",
            "figure": {}
        }
    }
    sanitized = sanitize_tool_payload(payload)
    data = json.loads(sanitized)

    assert data["success"] is False
    assert "figure" not in data["result"]
    assert data["result"]["chart_status"] == "Visualization generation failed."
    assert '"figure":' not in sanitized


def test_sanitize_tool_payload_nested_missing_figure_no_false_status():
    payload = {
        "success": True,
        "result": {
            "operation": "sum",
            "value": 9999
        }
    }
    sanitized = sanitize_tool_payload(payload)
    data = json.loads(sanitized)

    assert data["success"] is True
    assert "chart_status" not in data["result"]
    assert data["result"]["operation"] == "sum"


def test_sanitize_tool_payload_string_input():
    raw_json = json.dumps({
        "success": True,
        "result": {
            "chart_type": "histogram",
            "figure": {"data": [{"x": [1, 2, 3]}]}
        }
    })
    sanitized = sanitize_tool_payload(raw_json)
    data = json.loads(sanitized)

    assert "figure" not in data["result"]
    assert data["result"]["chart_status"] == "Visualization generated successfully."
    assert '"figure":' not in sanitized


def test_sanitize_tool_payload_non_json_string():
    raw_str = "Error: Database connection failed."
    sanitized = sanitize_tool_payload(raw_str)
    assert sanitized == raw_str


# --------------------------------------------------
# HAS_VALID_VISUALIZATION MALFORMED ENTRIES TESTS
# --------------------------------------------------

def test_has_valid_visualization_malformed_non_list():
    assert has_valid_visualization(None) is False
    assert has_valid_visualization("invalid") is False
    assert has_valid_visualization(123) is False
    assert has_valid_visualization({}) is False
    assert has_valid_visualization(True) is False
    assert has_valid_visualization(False) is False


def test_has_valid_visualization_empty_list():
    assert has_valid_visualization([]) is False


def test_has_valid_visualization_list_with_non_dict_elements():
    assert has_valid_visualization([None]) is False
    assert has_valid_visualization(["a string", 42]) is False
    assert has_valid_visualization([[1, 2, 3]]) is False


def test_has_valid_visualization_missing_tool_or_results():
    assert has_valid_visualization([{}]) is False
    assert has_valid_visualization([{"tool": "visualize_data"}]) is False
    assert has_valid_visualization([{"tool": "other_tool", "results": {"figure": {"data": [1]}}}]) is False


def test_has_valid_visualization_malformed_results_field():
    assert has_valid_visualization([{"tool": "visualize_data", "results": None}]) is False
    assert has_valid_visualization([{"tool": "visualize_data", "results": "string"}]) is False
    assert has_valid_visualization([{"tool": "visualize_data", "results": [1, 2, 3]}]) is False
    assert has_valid_visualization([{"tool": "visualize_data", "results": {}}]) is False
    assert has_valid_visualization([{"tool": "visualize_data", "results": {"figure": {}}}]) is False
    assert has_valid_visualization([{"tool": "visualize_data", "results": {"figure": None}}]) is False
    assert has_valid_visualization([{"tool": "visualize_data", "results": {"figure": "not a dict"}}]) is False
    assert has_valid_visualization([{"tool": "visualize_data", "results": {"figure": {"data": []}}}]) is False
    assert has_valid_visualization([{"tool": "visualize_data", "results": {"figure": {"data": [None]}}}]) is False
    assert has_valid_visualization([{"tool": "visualize_data", "results": {"figure": {"data": [{}]}}}]) is False


def test_has_valid_visualization_mixed_malformed_and_valid():
    tool_results = [
        None,
        "not a dict",
        {},
        {"tool": "aggregate_data", "results": {"mean": 50}},
        {"tool": "visualize_data", "results": {"figure": {}}},
        {"tool": "visualize_data", "results": {"figure": {"data": [{"x": [1, 2]}]}}}
    ]
    assert has_valid_visualization(tool_results) is True


def test_figure_data_removed_from_llm_messages_in_run_manager(monkeypatch, sample_df):
    tools = [{"type": "function", "function": {"name": "visualize_data"}}]

    responses = [
        make_message([make_tool_call("visualize_data", {"chart_type": "bar", "x_column": "City", "y_column": "Sales"})]),
        make_message(content="I have created the bar chart.")
    ]

    llm_received_messages = []

    def fake_ask_manager(messages, active_tools):
        llm_received_messages.append(json.loads(json.dumps(messages)))
        return responses.pop(0)

    def fake_executor(df, tool_call):
        return {
            "chart_type": "bar",
            "x_column": "City",
            "y_column": "Sales",
            "figure": {
                "data": [{"x": ["Delhi", "Mumbai"], "y": [1200, 800]}],
                "layout": {"title": "Sales by City"}
            }
        }

    monkeypatch.setattr("app.manager.ask_manager", fake_ask_manager)

    result = run_manager(
        sample_df,
        "Create a bar chart showing Sales by City.",
        tools,
        fake_executor
    )

    assert result["stop_reason"] == "completed"

    # Second call to ask_manager should contain the tool output without raw figure
    assert len(llm_received_messages) == 2
    second_call_messages = llm_received_messages[1]
    tool_msg = [m for m in second_call_messages if m.get("role") == "tool"][0]
    tool_content = tool_msg["content"]

    assert '"figure":' not in tool_content
    assert "Visualization generated successfully." in tool_content

    # In returned conversation_history, raw figure is also absent
    for msg in result["conversation_history"]:
        if msg.get("role") == "tool":
            assert '"figure":' not in msg.get("content", "")
            assert "Visualization generated successfully." in msg.get("content", "")

    # But figure IS preserved in tool_results for the frontend
    assert len(result["tool_results"]) == 1
    assert result["tool_results"][0]["results"]["figure"] is not None


# --------------------------------------------------
# RECURSIVE FIGURE SANITIZATION & IMMUTABILITY TESTS
# --------------------------------------------------

def test_sanitize_tool_payload_arbitrarily_nested_dict():
    payload = {
        "level1": {
            "level2": {
                "level3": {
                    "chart_name": "Deep Plot",
                    "figure": {
                        "data": [{"type": "bar", "x": ["A"], "y": [10]}],
                        "layout": {"title": "Deep"}
                    }
                },
                "other_info": "preserved"
            }
        }
    }
    sanitized = sanitize_tool_payload(payload)
    data = json.loads(sanitized)

    assert '"figure":' not in sanitized
    assert data["level1"]["level2"]["other_info"] == "preserved"
    level3 = data["level1"]["level2"]["level3"]
    assert level3["chart_name"] == "Deep Plot"
    assert "figure" not in level3
    assert level3["chart_status"] == "Visualization generated successfully."


def test_sanitize_tool_payload_nested_in_list_of_dicts():
    payload = {
        "charts": [
            {
                "id": "c1",
                "figure": {
                    "data": [{"type": "scatter", "x": [1, 2], "y": [3, 4]}]
                }
            },
            {
                "id": "c2",
                "figure": {
                    "data": []  # empty data -> invalid
                }
            }
        ]
    }
    sanitized = sanitize_tool_payload(payload)
    data = json.loads(sanitized)

    assert '"figure":' not in sanitized
    c1 = data["charts"][0]
    assert c1["id"] == "c1"
    assert "figure" not in c1
    assert c1["chart_status"] == "Visualization generated successfully."

    c2 = data["charts"][1]
    assert c2["id"] == "c2"
    assert "figure" not in c2
    assert c2["chart_status"] == "Visualization generation failed."


def test_sanitize_tool_payload_deeply_nested_lists_and_dicts():
    payload = {
        "pipeline": [
            [
                {
                    "stage": "visualization",
                    "output": {
                        "figure": {
                            "data": [{"type": "histogram", "x": [1, 2, 3]}]
                        },
                        "meta": {"created": True}
                    }
                }
            ]
        ]
    }
    sanitized = sanitize_tool_payload(payload)
    data = json.loads(sanitized)

    assert '"figure":' not in sanitized
    stage_output = data["pipeline"][0][0]["output"]
    assert "figure" not in stage_output
    assert stage_output["chart_status"] == "Visualization generated successfully."
    assert stage_output["meta"]["created"] is True


def test_sanitize_tool_payload_does_not_mutate_original_input():
    import copy
    original = {
        "status": "ok",
        "result": {
            "figure": {
                "data": [{"type": "bar", "x": [1, 2], "y": [3, 4]}],
                "layout": {"title": "Immutable"}
            },
            "extra": [1, 2, {"nested": True}]
        }
    }
    original_copy = copy.deepcopy(original)
    sanitized = sanitize_tool_payload(original)

    # Original object must not be mutated
    assert original == original_copy
    assert "figure" in original["result"]

    data = json.loads(sanitized)
    assert "figure" not in data["result"]
    assert data["result"]["chart_status"] == "Visualization generated successfully."


def test_sanitize_tool_payload_preserves_unrelated_complex_data():
    payload = {
        "status": 200,
        "metrics": [10.5, 20.3, 30.1],
        "metadata": {
            "tags": ["alpha", "beta"],
            "nested": {
                "active": True,
                "count": None
            }
        }
    }
    sanitized = sanitize_tool_payload(payload)
    data = json.loads(sanitized)

    assert data == payload
    assert "chart_status" not in str(data)


# --------------------------------------------------
# COMPOUND & NEGATED REQUEST TESTS
# --------------------------------------------------

def test_is_compound_query():
    assert is_compound_query("Calculate average Profit by Category and create a bar chart.") is True
    assert is_compound_query("Find total Sales by Region and plot a bar chart.") is True
    assert is_compound_query("Compute the correlation between Sales and Profit and create a scatter plot.") is True
    assert is_compound_query("Determine the average sales for each city and draw a histogram.") is True
    assert is_compound_query("Create a bar chart showing average Profit for each Category.") is False
    assert is_compound_query("Calculate average Profit by Category.") is False
    assert is_compound_query("What is the average sales for each city?") is False
    assert is_compound_query("Explain the previous chart") is False
    assert is_compound_query("Don't create a chart; just calculate average profit") is False


def test_compound_analytical_request_executes_both_tools(monkeypatch, sample_df):
    tools = [
        {"type": "function", "function": {"name": "aggregate_data"}},
        {"type": "function", "function": {"name": "visualize_data"}}
    ]

    captured_tools = []
    responses = [
        make_message([
            make_tool_call("aggregate_data", {
                "group_column": "City",
                "target_column": "Sales",
                "operation": "mean"
            })
        ]),
        make_message([
            make_tool_call("visualize_data", {
                "chart_type": "bar",
                "x_column": "City",
                "y_column": "Sales",
                "aggregation": "mean"
            })
        ]),
        make_message(content="Calculated average sales and created the bar chart.")
    ]

    def fake_ask_manager(messages, active_tools):
        captured_tools.append(active_tools)
        return responses.pop(0)

    def fake_executor_compound(df, tool_call):
        name = tool_call["function"]["name"]
        if name == "aggregate_data":
            return [{"City": "Delhi", "result": 600}, {"City": "Mumbai", "result": 800}]
        elif name == "visualize_data":
            return {
                "chart_type": "bar",
                "x_column": "City",
                "y_column": "Sales",
                "aggregation": "mean",
                "figure": {"data": [{"type": "bar", "x": ["Delhi", "Mumbai"], "y": [600, 800]}]}
            }
        raise ValueError(f"Unknown tool: {name}")

    monkeypatch.setattr("app.manager.ask_manager", fake_ask_manager)

    result = run_manager(
        sample_df,
        "Calculate average Profit by Category and create a bar chart.",
        tools,
        fake_executor_compound
    )

    # Both tools must be in active_tools for a compound query
    assert len(captured_tools[0]) == 2
    tool_names = [t["function"]["name"] for t in captured_tools[0]]
    assert "aggregate_data" in tool_names
    assert "visualize_data" in tool_names

    # Both tools must have executed successfully
    assert result["tool_calls_count"] == 2
    executed_tools = [tr["tool"] for tr in result["tool_results"]]
    assert executed_tools == ["aggregate_data", "visualize_data"]
    assert result["stop_reason"] == "completed"
    assert has_valid_visualization(result["tool_results"]) is True


def test_negated_visualization_request_executes_only_numerical_tool(monkeypatch, sample_df):
    tools = [
        {"type": "function", "function": {"name": "aggregate_data"}},
        {"type": "function", "function": {"name": "visualize_data"}}
    ]

    captured_tools = []
    responses = [
        make_message([
            make_tool_call("aggregate_data", {
                "group_column": "City",
                "target_column": "Sales",
                "operation": "mean"
            })
        ]),
        make_message(content="Average sales calculated without a chart.")
    ]

    def fake_ask_manager(messages, active_tools):
        captured_tools.append(active_tools)
        return responses.pop(0)

    def fake_executor_num(df, tool_call):
        return [{"City": "Delhi", "result": 600}, {"City": "Mumbai", "result": 800}]

    monkeypatch.setattr("app.manager.ask_manager", fake_ask_manager)

    result = run_manager(
        sample_df,
        "Don't create a chart; just calculate average profit",
        tools,
        fake_executor_num
    )

    # All tools available, not restricted to visualize_data
    assert len(captured_tools[0]) == 2
    assert result["tool_calls_count"] == 1
    assert result["tool_results"][0]["tool"] == "aggregate_data"
    assert result["stop_reason"] == "completed"


# --------------------------------------------------
# UNRELATED FIGURE FIELD SANITIZATION TESTS
# --------------------------------------------------

def test_sanitize_tool_payload_preserves_unrelated_figure_string():
    payload = {
        "report": "Q3 Analysis",
        "figure": "Figure 1: Revenue Over Time",
        "total_revenue": 1500000
    }
    sanitized = sanitize_tool_payload(payload)
    data = json.loads(sanitized)

    assert data["figure"] == "Figure 1: Revenue Over Time"
    assert data["total_revenue"] == 1500000
    assert "chart_status" not in data


def test_sanitize_tool_payload_preserves_unrelated_figure_number():
    payload = {
        "metric": "Sales",
        "figure": 42500,
        "units": "USD"
    }
    sanitized = sanitize_tool_payload(payload)
    data = json.loads(sanitized)

    assert data["figure"] == 42500
    assert data["units"] == "USD"
    assert "chart_status" not in data


def test_sanitize_tool_payload_preserves_unrelated_figure_dict():
    payload = {
        "catalog": "action figures",
        "figure": {
            "model_name": "Titan",
            "scale": "1:18",
            "accessories": ["shield", "sword"]
        }
    }
    sanitized = sanitize_tool_payload(payload)
    data = json.loads(sanitized)

    assert data["figure"] == {
        "model_name": "Titan",
        "scale": "1:18",
        "accessories": ["shield", "sword"]
    }
    assert "chart_status" not in data


def test_sanitize_tool_payload_mixed_real_and_unrelated_figure():
    payload = {
        "chart_type": "bar",
        "figure": {
            "data": [{"type": "bar", "x": ["North", "South"], "y": [100, 200]}],
            "layout": {"title": "Sales"}
        },
        "caption": {
            "figure": "Figure 2.4",
            "page": 12
        }
    }
    sanitized = sanitize_tool_payload(payload)
    data = json.loads(sanitized)

    # Top-level Plotly figure stripped and chart_status added
    assert "figure" not in data
    assert data["chart_status"] == "Visualization generated successfully."

    # Nested unrelated figure string preserved
    assert data["caption"]["figure"] == "Figure 2.4"
    assert data["caption"]["page"] == 12
    assert "chart_status" not in data["caption"]
    assert '"data":' not in sanitized
