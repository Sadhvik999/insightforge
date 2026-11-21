
import pandas as pd
import pytest

from app.agent import create_tools, execute_tool, analyze_dataset


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "City": [
            "Delhi",
            "Mumbai",
            "Chennai",
            "Delhi",
            "Mumbai"
        ],
        "Sales": [500, 800, 400, 700, 900],
        "Profit": [100, 200, 80, 150, 250]
    })


def make_tool_call(name, arguments):
    return {
        "function": {
            "name": name,
            "arguments": arguments
        }
    }


# DAY 9 TESTS


def test_create_tools(sample_df):
    tools = create_tools(sample_df)

    tool_names = [
        tool["function"]["name"]
        for tool in tools
    ]

    assert len(tool_names) == 6

    assert "get_dataset_summary" in tool_names
    assert "get_column_info" in tool_names
    assert "filter_data" in tool_names
    assert "aggregate_data" in tool_names
    assert "correlation_analysis" in tool_names
    assert "visualize_data" in tool_names


def test_dataset_summary_tool(sample_df):
    call = make_tool_call(
        "get_dataset_summary",
        {}
    )

    result = execute_tool(sample_df, call)

    assert result["total_rows"] == 5
    assert result["total_columns"] == 3
    assert result["total_missing_values"] == 0


def test_column_info_tool(sample_df):
    call = make_tool_call(
        "get_column_info",
        {}
    )

    result = execute_tool(sample_df, call)

    assert "City" in result
    assert "Sales" in result
    assert result["Sales"]["is_numeric"] is True


def test_filter_tool(sample_df):
    call = make_tool_call(
        "filter_data",
        {
            "column": "Sales",
            "operator": "gt",
            "value": 600
        }
    )

    result = execute_tool(sample_df, call)

    assert len(result) == 3

    assert all(
        row["Sales"] > 600
        for row in result
    )


def test_aggregate_tool(sample_df):
    call = make_tool_call(
        "aggregate_data",
        {
            "group_column": "City",
            "target_column": "Sales",
            "operation": "mean"
        }
    )

    result = execute_tool(sample_df, call)

    assert len(result) == 3

    city_results = {
        row["City"]: row["result"]
        for row in result
    }

    assert city_results["Delhi"] == 600
    assert city_results["Mumbai"] == 850
    assert city_results["Chennai"] == 400


def test_correlation_tool(sample_df):
    call = make_tool_call(
        "correlation_analysis",
        {
            "columns": ["Sales", "Profit"],
            "method": "pearson"
        }
    )

    result = execute_tool(sample_df, call)

    assert "Sales" in result
    assert "Profit" in result["Sales"]

    assert result["Sales"]["Sales"] == pytest.approx(1.0)


def test_invalid_tool(sample_df):
    call = make_tool_call(
        "unknown_tool",
        {}
    )

    with pytest.raises(ValueError):
        execute_tool(sample_df, call)


def test_invalid_filter_column(sample_df):
    call = make_tool_call(
        "filter_data",
        {
            "column": "Unknown",
            "operator": "gt",
            "value": 100
        }
    )

    with pytest.raises(ValueError):
        execute_tool(sample_df, call)


def test_invalid_aggregation_column(sample_df):
    call = make_tool_call(
        "aggregate_data",
        {
            "group_column": "City",
            "target_column": "Unknown",
            "operation": "mean"
        }
    )

    with pytest.raises(ValueError):
        execute_tool(sample_df, call)


def test_invalid_correlation_column(sample_df):
    call = make_tool_call(
        "correlation_analysis",
        {
            "columns": ["Sales", "Unknown"],
            "method": "pearson"
        }
    )

    with pytest.raises(ValueError):
        execute_tool(sample_df, call)


# DAY 10 VISUALIZATION TESTS


def test_bar_visualization(sample_df):
    call = make_tool_call(
        "visualize_data",
        {
            "chart_type": "bar",
            "x_column": "City",
            "y_column": "Sales",
            "title": "Sales by City"
        }
    )

    result = execute_tool(sample_df, call)

    assert result["chart_type"] == "bar"
    assert result["x_column"] == "City"
    assert result["y_column"] == "Sales"
    assert result["title"] == "Sales by City"

    assert "figure" in result
    assert result["figure"]["data"][0]["type"] == "bar"


def test_line_visualization(sample_df):
    call = make_tool_call(
        "visualize_data",
        {
            "chart_type": "line",
            "x_column": "City",
            "y_column": "Sales"
        }
    )

    result = execute_tool(sample_df, call)

    assert result["chart_type"] == "line"
    assert result["figure"]["data"][0]["type"] == "scatter"


def test_histogram_visualization(sample_df):
    call = make_tool_call(
        "visualize_data",
        {
            "chart_type": "histogram",
            "x_column": "Sales"
        }
    )

    result = execute_tool(sample_df, call)

    assert result["chart_type"] == "histogram"
    assert result["x_column"] == "Sales"
    assert result["figure"]["data"][0]["type"] == "histogram"


def test_scatter_visualization(sample_df):
    call = make_tool_call(
        "visualize_data",
        {
            "chart_type": "scatter",
            "x_column": "Sales",
            "y_column": "Profit"
        }
    )

    result = execute_tool(sample_df, call)

    assert result["chart_type"] == "scatter"
    assert result["x_column"] == "Sales"
    assert result["y_column"] == "Profit"
    assert result["figure"]["data"][0]["type"] == "scatter"


def test_invalid_visualization_column(sample_df):
    call = make_tool_call(
        "visualize_data",
        {
            "chart_type": "bar",
            "x_column": "Unknown",
            "y_column": "Sales"
        }
    )

    with pytest.raises(ValueError):
        execute_tool(sample_df, call)


def get_trace_y(trace):
    y = trace["y"]
    if isinstance(y, dict) and "bdata" in y:
        import base64
        import numpy as np
        return list(np.frombuffer(base64.b64decode(y["bdata"]), dtype=y["dtype"]))
    return list(y)


def test_bar_visualization_aggregates_sums_by_category(sample_df):
    call = make_tool_call(
        "visualize_data",
        {
            "chart_type": "bar",
            "x_column": "City",
            "y_column": "Sales"
        }
    )

    result = execute_tool(sample_df, call)
    trace = result["figure"]["data"][0]

    # Exactly one bar per unique category (no horizontal stripes/stacked rows)
    assert len(trace["x"]) == 3
    y_values = get_trace_y(trace)
    assert len(y_values) == 3

    city_totals = dict(zip(trace["x"], y_values))
    assert city_totals["Delhi"] == 1200  # 500 + 700
    assert city_totals["Mumbai"] == 1700  # 800 + 900
    assert city_totals["Chennai"] == 400


def test_bar_visualization_supports_mean_aggregation(sample_df):
    call = make_tool_call(
        "visualize_data",
        {
            "chart_type": "bar",
            "x_column": "City",
            "y_column": "Sales",
            "aggregation": "mean"
        }
    )

    result = execute_tool(sample_df, call)
    trace = result["figure"]["data"][0]

    assert len(trace["x"]) == 3
    y_values = get_trace_y(trace)
    city_means = dict(zip(trace["x"], y_values))
    assert city_means["Delhi"] == 600.0  # (500 + 700) / 2
    assert city_means["Mumbai"] == 850.0  # (800 + 900) / 2
    assert city_means["Chennai"] == 400.0


def test_bar_visualization_without_duplicate_categories():
    df = pd.DataFrame({
        "Country": ["USA", "Canada", "Mexico"],
        "Revenue": [1000, 500, 300]
    })
    call = make_tool_call(
        "visualize_data",
        {
            "chart_type": "bar",
            "x_column": "Country",
            "y_column": "Revenue"
        }
    )

    result = execute_tool(df, call)
    trace = result["figure"]["data"][0]

    assert len(trace["x"]) == 3
    y_values = get_trace_y(trace)
    country_revenue = dict(zip(trace["x"], y_values))
    assert country_revenue["USA"] == 1000
    assert country_revenue["Canada"] == 500
    assert country_revenue["Mexico"] == 300


def test_analyze_dataset_fails_gracefully_when_visualization_fails(
    monkeypatch,
    sample_df
):
    def fake_run_manager(*args, **kwargs):
        return {
            "tool_results": [],
            "tool_calls_count": 1,
            "final_message": "The requested visualization could not be generated.",
            "stop_reason": "visualization_failed",
            "conversation_history": []
        }

    monkeypatch.setattr("app.agent.run_manager", fake_run_manager)

    with pytest.raises(ValueError) as excinfo:
        analyze_dataset(
            sample_df,
            "Create a bar chart of Sales by NonExistentColumn."
        )

    assert "could not be generated" in str(excinfo.value)
    assert "successfully" not in str(excinfo.value)


def test_analyze_dataset_valid_figure(monkeypatch, sample_df):
    figure_data = {"data": [{"x": ["Delhi", "Mumbai"], "y": [500, 800]}], "layout": {}}
    def fake_run_manager(*args, **kwargs):
        return {
            "tool_results": [{
                "tool": "visualize_data",
                "arguments": {"chart_type": "bar", "x_column": "City", "y_column": "Sales"},
                "results": {
                    "chart_type": "bar",
                    "x_column": "City",
                    "y_column": "Sales",
                    "figure": figure_data
                }
            }],
            "tool_calls_count": 1,
            "final_message": "Visualization generated.",
            "stop_reason": "completed",
            "conversation_history": []
        }

    monkeypatch.setattr("app.agent.run_manager", fake_run_manager)

    response = analyze_dataset(
        sample_df,
        "Create a bar chart showing Sales by City."
    )

    assert response["selected_tool"] == "visualize_data"
    # Preserves valid figures in tool_results / results for the frontend
    assert response["results"]["figure"] == figure_data
    assert response["tool_results"][0]["results"]["figure"] == figure_data


def test_analyze_dataset_missing_figure_raises(monkeypatch, sample_df):
    def fake_run_manager(*args, **kwargs):
        return {
            "tool_results": [{
                "tool": "visualize_data",
                "arguments": {"chart_type": "bar", "x_column": "City", "y_column": "Sales"},
                "results": {
                    "chart_type": "bar",
                    "x_column": "City",
                    "y_column": "Sales"
                    # missing 'figure'
                }
            }],
            "tool_calls_count": 1,
            "final_message": "The requested visualization could not be generated.",
            "stop_reason": "visualization_failed",
            "conversation_history": []
        }

    monkeypatch.setattr("app.agent.run_manager", fake_run_manager)

    with pytest.raises(ValueError) as excinfo:
        analyze_dataset(
            sample_df,
            "Create a bar chart showing Sales by City."
        )

    assert "could not be generated" in str(excinfo.value)
    assert "successfully" not in str(excinfo.value)


def test_analyze_dataset_empty_figure_raises(monkeypatch, sample_df):
    def fake_run_manager(*args, **kwargs):
        return {
            "tool_results": [{
                "tool": "visualize_data",
                "arguments": {"chart_type": "bar", "x_column": "City", "y_column": "Sales"},
                "results": {
                    "chart_type": "bar",
                    "x_column": "City",
                    "y_column": "Sales",
                    "figure": {}  # empty dict figure
                }
            }],
            "tool_calls_count": 1,
            "final_message": "The requested visualization could not be generated.",
            "stop_reason": "visualization_failed",
            "conversation_history": []
        }

    monkeypatch.setattr("app.agent.run_manager", fake_run_manager)

    with pytest.raises(ValueError) as excinfo:
        analyze_dataset(
            sample_df,
            "Create a bar chart showing Sales by City."
        )

    assert "could not be generated" in str(excinfo.value)
    assert "successfully" not in str(excinfo.value)


def test_analyze_dataset_executor_exception_raises(monkeypatch, sample_df):
    def fake_run_manager(*args, **kwargs):
        return {
            "tool_results": [],
            "tool_calls_count": 1,
            "final_message": "The requested visualization could not be generated.",
            "stop_reason": "visualization_failed",
            "conversation_history": []
        }

    monkeypatch.setattr("app.agent.run_manager", fake_run_manager)

    with pytest.raises(ValueError) as excinfo:
        analyze_dataset(
            sample_df,
            "Plot Sales vs City."
        )

    assert "could not be generated" in str(excinfo.value)


def test_analyze_dataset_ordinary_aggregation_unaffected(monkeypatch, sample_df):
    def fake_run_manager(*args, **kwargs):
        return {
            "tool_results": [{
                "tool": "aggregate_data",
                "arguments": {"group_column": "City", "target_column": "Sales", "operation": "mean"},
                "results": [{"City": "Delhi", "result": 600}]
            }],
            "tool_calls_count": 1,
            "final_message": "Mean sales calculated.",
            "stop_reason": "completed",
            "conversation_history": []
        }

    monkeypatch.setattr("app.agent.run_manager", fake_run_manager)

    response = analyze_dataset(
        sample_df,
        "What is the average sales for each city?"
    )

    assert response["selected_tool"] == "aggregate_data"
    assert "Delhi" in response["summary"]
    assert response["stop_reason"] == "completed"


def test_analyze_dataset_compound_request(monkeypatch, sample_df):
    figure_data = {"data": [{"x": ["Delhi", "Mumbai"], "y": [600, 800]}], "layout": {}}
    def fake_run_manager(*args, **kwargs):
        return {
            "tool_results": [
                {
                    "tool": "aggregate_data",
                    "arguments": {"group_column": "City", "target_column": "Sales", "operation": "mean"},
                    "results": [{"City": "Delhi", "result": 600}, {"City": "Mumbai", "result": 800}]
                },
                {
                    "tool": "visualize_data",
                    "arguments": {"chart_type": "bar", "x_column": "City", "y_column": "Sales", "aggregation": "mean"},
                    "results": {
                        "chart_type": "bar",
                        "x_column": "City",
                        "y_column": "Sales",
                        "aggregation": "mean",
                        "figure": figure_data
                    }
                }
            ],
            "tool_calls_count": 2,
            "final_message": "Calculated the average sales and created the bar chart.",
            "stop_reason": "completed",
            "conversation_history": []
        }

    monkeypatch.setattr("app.agent.run_manager", fake_run_manager)

    response = analyze_dataset(
        sample_df,
        "Calculate average Profit by Category and create a bar chart."
    )

    assert len(response["tool_results"]) == 2
    assert response["tool_results"][0]["tool"] == "aggregate_data"
    assert response["tool_results"][1]["tool"] == "visualize_data"
    assert response["tool_results"][1]["results"]["figure"] == figure_data
    assert response["stop_reason"] == "completed"


def test_execute_tool_aggregate_overall(sample_df):
    call = make_tool_call(
        "aggregate_data",
        {
            "target_column": "Sales",
            "operation": "sum"
        }
    )
    result = execute_tool(sample_df, call)
    assert len(result) == 1
    assert result[0]["result"] == 3300


def test_execute_tool_aggregate_fallback_from_group_column(sample_df):
    call = make_tool_call(
        "aggregate_data",
        {
            "group_column": "Sales",
            "operation": "sum"
        }
    )
    result = execute_tool(sample_df, call)
    assert len(result) == 1
    assert result[0]["result"] == 3300


def test_execute_tool_invalid_target_column(sample_df):
    call = make_tool_call(
        "aggregate_data",
        {
            "target_column": "UnknownCol",
            "operation": "sum"
        }
    )
    with pytest.raises(ValueError):
        execute_tool(sample_df, call)


def test_analyze_dataset_multi_metric_sales_and_profit(monkeypatch, sample_df):
    def fake_run_manager(*args, **kwargs):
        return {
            "tool_results": [
                {
                    "tool": "aggregate_data",
                    "arguments": {"target_column": "Sales", "operation": "sum"},
                    "results": [{"result": 3300.0}]
                },
                {
                    "tool": "aggregate_data",
                    "arguments": {"target_column": "Profit", "operation": "sum"},
                    "results": [{"result": 780.0}]
                }
            ],
            "tool_calls_count": 2,
            "final_message": "Total sales is 3,300.00 and total profit is 780.00.",
            "stop_reason": "completed",
            "conversation_history": []
        }

    monkeypatch.setattr("app.agent.run_manager", fake_run_manager)

    response = analyze_dataset(
        sample_df,
        "What are the total sales and total profit in this dataset?"
    )

    assert len(response["tool_results"]) == 2
    assert all(r["tool"] == "aggregate_data" for r in response["tool_results"])
    assert "Sales" in response["summary"]
    assert "Profit" in response["summary"]
    assert "3,300" in response["summary"]
    assert "780" in response["summary"]
    assert len(response["key_findings"]) >= 2
    assert any("Sales" in f for f in response["key_findings"])
    assert any("Profit" in f for f in response["key_findings"])
    assert response["stop_reason"] == "completed"


def test_analyze_dataset_multi_metric_average_sales_and_profit(monkeypatch, sample_df):
    def fake_run_manager(*args, **kwargs):
        return {
            "tool_results": [
                {
                    "tool": "aggregate_data",
                    "arguments": {"target_column": "Sales", "operation": "mean"},
                    "results": [{"result": 660.0}]
                },
                {
                    "tool": "aggregate_data",
                    "arguments": {"target_column": "Profit", "operation": "mean"},
                    "results": [{"result": 156.0}]
                }
            ],
            "tool_calls_count": 2,
            "final_message": "Average sales is 660.00 and average profit is 156.00.",
            "stop_reason": "completed",
            "conversation_history": []
        }

    monkeypatch.setattr("app.agent.run_manager", fake_run_manager)

    response = analyze_dataset(
        sample_df,
        "What are the average sales and average profit in this dataset?"
    )

    assert len(response["tool_results"]) == 2
    assert all(r["tool"] == "aggregate_data" for r in response["tool_results"])
    assert "Sales" in response["summary"]
    assert "Profit" in response["summary"]
    assert "660" in response["summary"]
    assert "156" in response["summary"]
    assert len(response["key_findings"]) >= 2
    assert any("Sales" in f for f in response["key_findings"])
    assert any("Profit" in f for f in response["key_findings"])
    assert response["stop_reason"] == "completed"


def test_analyze_dataset_single_metric_overall(monkeypatch, sample_df):
    def fake_run_manager(*args, **kwargs):
        return {
            "tool_results": [
                {
                    "tool": "aggregate_data",
                    "arguments": {"target_column": "Sales", "operation": "sum"},
                    "results": [{"result": 3300.0}]
                }
            ],
            "tool_calls_count": 1,
            "final_message": "The total Sales is 3,300.00.",
            "stop_reason": "completed",
            "conversation_history": []
        }

    monkeypatch.setattr("app.agent.run_manager", fake_run_manager)

    response = analyze_dataset(
        sample_df,
        "What is the total sales in this dataset?"
    )

    assert response["selected_tool"] == "aggregate_data"
    assert len(response["tool_results"]) == 1
    assert "Sales" in response["summary"]
    assert "3,300" in response["summary"]
    assert response["results"] == [{"result": 3300.0}]
    assert response["stop_reason"] == "completed"


def test_analyze_dataset_invalid_column_handling(monkeypatch, sample_df):
    def fake_run_manager(*args, **kwargs):
        return {
            "tool_results": [],
            "tool_calls_count": 1,
            "final_message": "It seems there was an error with the target column. Could you please specify the correct column name for revenue?",
            "stop_reason": "completed",
            "conversation_history": []
        }

    monkeypatch.setattr("app.agent.run_manager", fake_run_manager)

    with pytest.raises(ValueError) as excinfo:
        analyze_dataset(sample_df, "What is the total revenue?")

    assert "Could you please specify the correct column name" in str(excinfo.value)


def test_analyze_dataset_multi_turn_aggregation(monkeypatch, sample_df):
    captured_kwargs = {}

    def fake_run_manager(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return {
            "tool_results": [
                {
                    "tool": "aggregate_data",
                    "arguments": {"target_column": "Profit", "operation": "sum"},
                    "results": [{"result": 780.0}]
                }
            ],
            "tool_calls_count": 1,
            "final_message": "The total Profit is 780.00.",
            "stop_reason": "completed",
            "conversation_history": []
        }

    monkeypatch.setattr("app.agent.run_manager", fake_run_manager)

    history = [
        {"role": "user", "content": "What is the total sales?"},
        {"role": "assistant", "content": "The total Sales is 3,300.00."}
    ]

    response = analyze_dataset(
        sample_df,
        "And what is the total profit?",
        conversation_history=history
    )

    assert captured_kwargs.get("conversation_history") == history
    assert response["selected_tool"] == "aggregate_data"
    assert "Profit" in response["summary"]
    assert "780" in response["summary"]
