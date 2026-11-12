import json
import requests
import pandas as pd

from app.tools import (
    get_column_info,
    get_dataset_summary,
    filter_data,
    aggregate_data
)

from app.analyzer import correlation_analysis
from app.visualizer import create_visualization
from app.manager import run_manager
from app.response_generator import generate_multi_analysis_response


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5:1.5b"


# --------------------------------------------------
# CREATE DYNAMIC TOOL DEFINITIONS
# --------------------------------------------------

def create_tools(df):
    """Create available AI tools based on dataset columns."""

    all_columns = df.columns.tolist()

    numerical_columns = df.select_dtypes(
        include="number"
    ).columns.tolist()

    if not all_columns:
        raise ValueError("Dataset has no columns.")

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_dataset_summary",
                "description": "Get an overall dataset summary including rows, columns, missing values and duplicates.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_column_info",
                "description": "Get data types, missing values and unique values for every column.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "filter_data",
                "description": "Filter dataset rows using a column, comparison operator and value.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "column": {
                            "type": "string",
                            "enum": all_columns
                        },
                        "operator": {
                            "type": "string",
                            "enum": [
                                "eq", "ne", "gt", "gte",
                                "lt", "lte", "contains",
                                "in", "not_in",
                                "is_null", "not_null"
                            ]
                        },
                        "value": {
                            "type": [
                                "string", "number", "array", "null"
                            ]
                        }
                    },
                    "required": ["column", "operator"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "aggregate_data",
                "description": "Group the dataset by a column and calculate mean, sum, min, max or count.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "group_column": {
                            "type": "string",
                            "enum": all_columns
                        },
                        "target_column": {
                            "type": "string",
                            "enum": all_columns
                        },
                        "operation": {
                            "type": "string",
                            "enum": [
                                "mean", "sum", "min", "max", "count"
                            ]
                        }
                    },
                    "required": [
                        "group_column", "target_column", "operation"
                    ]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "correlation_analysis",
                "description": "Calculate correlations between numerical dataset columns.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "columns": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": numerical_columns
                            }
                        },
                        "method": {
                            "type": "string",
                            "enum": ["pearson", "spearman", "kendall"]
                        }
                    },
                    "required": ["method"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "visualize_data",
                "description": (
                    "Create a chart from the dataset. "
                    "Choose bar for category comparisons, "
                    "line for trends, histogram for distributions, "
                    "and scatter for relationships between two numerical columns."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chart_type": {
                            "type": "string",
                            "enum": ["bar", "line", "histogram", "scatter"]
                        },
                        "x_column": {
                            "type": "string",
                            "enum": all_columns
                        },
                        "y_column": {
                            "type": ["string", "null"],
                            "enum": all_columns + [None]
                        },
                        "title": {
                            "type": ["string", "null"]
                        }
                    },
                    "required": ["chart_type", "x_column"]
                }
            }
        }
    ]

    return tools


# --------------------------------------------------
# ASK QWEN TO SELECT A TOOL
# --------------------------------------------------

def ask_qwen(df, question, tools):
    """Send the question and dataset schema to Qwen."""

    schema = {
        "columns": df.columns.tolist(),
        "numerical_columns": df.select_dtypes(
            include="number"
        ).columns.tolist(),
        "categorical_columns": df.select_dtypes(
            include=["object", "str", "category", "bool"]
        ).columns.tolist()
    }

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an AI data analyst. "
                    "Choose the most appropriate available Python tool. "
                    "Use exact column names from the dataset. "
                    "Never invent column names or results. "
                    "Use only one tool per question. "
                    "For visualization questions, use visualize_data. "
                    "For histogram, provide only x_column. "
                    "For bar, line and scatter, provide both x_column and y_column. "
                    f"Dataset schema: {schema}"
                )
            },
            {
                "role": "user",
                "content": question
            }
        ],
        "tools": tools,
        "stream": False,
        "options": {
            "temperature": 0
        }
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=120
        )

        response.raise_for_status()

        return response.json()["message"]

    except requests.exceptions.RequestException as e:
        raise RuntimeError(
            f"Could not communicate with Ollama: {e}"
        )


# --------------------------------------------------
# VALIDATE AND EXECUTE TOOL
# --------------------------------------------------

def execute_tool(df, tool_call):
    """Validate and execute an approved Python tool."""

    function_name = tool_call["function"]["name"]
    arguments = tool_call["function"]["arguments"]

    if not isinstance(arguments, dict):
        raise ValueError("Invalid tool arguments.")

    if function_name == "get_dataset_summary":
        return get_dataset_summary(df)

    elif function_name == "get_column_info":
        return get_column_info(df)

    elif function_name == "filter_data":

        column = arguments.get("column")
        operator = arguments.get("operator")
        value = arguments.get("value")

        if column not in df.columns:
            raise ValueError("Invalid filter column.")

        if operator not in [
            "eq", "ne", "gt", "gte", "lt", "lte",
            "contains", "in", "not_in",
            "is_null", "not_null"
        ]:
            raise ValueError("Invalid filter operator.")

        if pd.api.types.is_numeric_dtype(df[column]):
            if operator in ["in", "not_in"] and isinstance(value, list):
                value = [float(v) for v in value]
            elif operator not in ["is_null", "not_null"]:
                value = float(value)

        result_df = filter_data(
            df,
            column=column,
            operator=operator,
            value=value
        )

        return result_df.to_dict(orient="records")

    elif function_name == "aggregate_data":

        group_column = arguments.get("group_column")
        target_column = arguments.get("target_column")
        operation = arguments.get("operation")

        if group_column not in df.columns:
            raise ValueError("Invalid group column.")

        if target_column not in df.columns:
            raise ValueError("Invalid target column.")

        if operation not in [
            "mean", "sum", "min", "max", "count"
        ]:
            raise ValueError("Invalid aggregation operation.")

        result_df = aggregate_data(
            df,
            group_column=group_column,
            target_column=target_column,
            operation=operation
        )

        return result_df.to_dict(orient="records")

    elif function_name == "correlation_analysis":

        columns = arguments.get("columns")
        method = arguments.get("method", "pearson")

        if method not in ["pearson", "spearman", "kendall"]:
            raise ValueError("Invalid correlation method.")

        numerical_columns = df.select_dtypes(
            include="number"
        ).columns.tolist()

        if columns is not None:

            if not isinstance(columns, list):
                raise ValueError("Columns must be a list.")

            if any(column not in numerical_columns for column in columns):
                raise ValueError("Invalid numerical column.")

            if len(columns) < 2:
                raise ValueError(
                    "At least two numerical columns are required."
                )

        elif len(numerical_columns) < 2:
            raise ValueError(
                "At least two numerical columns are required."
            )

        result_df = correlation_analysis(
            df,
            columns=columns,
            method=method
        )

        return result_df.to_dict()

    elif function_name == "visualize_data":

        chart_type = arguments.get("chart_type")
        x_column = arguments.get("x_column")
        y_column = arguments.get("y_column")
        title = arguments.get("title")

        if chart_type not in [
            "bar", "line", "histogram", "scatter"
        ]:
            raise ValueError("Invalid chart type.")

        if x_column not in df.columns:
            raise ValueError("Invalid x column.")

        if y_column is not None and y_column not in df.columns:
            raise ValueError("Invalid y column.")

        if chart_type in ["bar", "line", "scatter"]:

            if y_column is None:
                raise ValueError(
                    f"{chart_type} chart requires a y column."
                )

            if not pd.api.types.is_numeric_dtype(df[y_column]):
                raise ValueError(
                    "The y column must be numerical for this chart."
                )

        if chart_type == "histogram":

            if not pd.api.types.is_numeric_dtype(df[x_column]):
                raise ValueError(
                    "Histogram requires a numerical x column."
                )

        if chart_type == "scatter":

            if not pd.api.types.is_numeric_dtype(df[x_column]):
                raise ValueError(
                    "Scatter chart requires a numerical x column."
                )

        fig = create_visualization(
            df,
            chart_type=chart_type,
            x_column=x_column,
            y_column=y_column,
            title=title
        )

        figure_data = json.loads(fig.to_json())

        return {
            "chart_type": chart_type,
            "x_column": x_column,
            "y_column": y_column,
            "title": title,
            "figure": figure_data
        }

    else:
        raise ValueError(
            f"Unsupported tool: {function_name}"
        )


# --------------------------------------------------
# MAIN DATASET ANALYSIS FUNCTION
# --------------------------------------------------


def analyze_dataset(df, question):
    """
    Complete multi-step AI agent workflow:

    1. Validate the dataset and question.
    2. Create available tools dynamically.
    3. Let the Manager Agent select and execute tools.
    4. Collect results from all executed tools.
    5. Generate one structured response.
    6. Return the complete analysis.
    """

    if df.empty:
        raise ValueError("Cannot analyze an empty dataset.")

    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    # Create the six approved tools dynamically.
    tools = create_tools(df)

    # Let the Manager Agent execute multiple tools.
    manager_result = run_manager(
        df=df,
        question=question,
        tools=tools,
        tool_executor=execute_tool
    )

    tool_results = manager_result["tool_results"]

    if not tool_results:
        raise ValueError(
            "The AI could not execute any valid analysis tools."
        )

    # Generate one response from all collected results.
    explanation = generate_multi_analysis_response(
        question=question,
        tool_results=tool_results,
        final_message=manager_result["final_message"]
    )

    # Preserve the original single-tool response fields
    # when only one tool was executed.
    single_tool = len(tool_results) == 1

    return {
        "question": question,
        "selected_tool": (
            tool_results[0]["tool"] if single_tool else None
        ),
        "arguments": (
            tool_results[0]["arguments"] if single_tool else None
        ),
        "summary": explanation["summary"],
        "key_findings": explanation["key_findings"],
        "results": (
            tool_results[0]["results"] if single_tool else None
        ),
        "tool_results": tool_results,
        "tool_calls_count": manager_result["tool_calls_count"],
        "stop_reason": manager_result["stop_reason"]
    }
