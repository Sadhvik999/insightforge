
import pandas as pd
import pytest

from app.agent import create_tools, execute_tool


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
