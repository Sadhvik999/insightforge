
import requests
import pandas as pd

from app.tools import aggregate_data


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5:1.5b"


# --------------------------------------------------
# CREATE DYNAMIC TOOL DEFINITIONS
# --------------------------------------------------

def create_tools(df):
    """
    Create tool definitions based on the uploaded dataset.
    """

    all_columns = df.columns.tolist()

    numerical_columns = df.select_dtypes(
        include="number"
    ).columns.tolist()

    if not all_columns:
        raise ValueError("Dataset has no columns.")

    if not numerical_columns:
        raise ValueError(
            "Dataset must contain at least one numerical column."
        )

    tools = [
        {
            "type": "function",
            "function": {
                "name": "aggregate_data",
                "description": (
                    "Group a dataset by a column and calculate "
                    "mean, sum, min, max, or count."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "group_column": {
                            "type": "string",
                            "enum": all_columns
                        },
                        "target_column": {
                            "type": "string",
                            "enum": numerical_columns
                        },
                        "operation": {
                            "type": "string",
                            "enum": [
                                "mean",
                                "sum",
                                "min",
                                "max",
                                "count"
                            ]
                        }
                    },
                    "required": [
                        "group_column",
                        "target_column",
                        "operation"
                    ]
                }
            }
        }
    ]

    return tools


# --------------------------------------------------
# ASK QWEN TO SELECT A TOOL
# --------------------------------------------------

def ask_qwen(df, question, tools):
    """
    Send the user's question and dataset schema to Qwen.
    """

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
                    "Understand the user's question and select "
                    "the appropriate available Python tool. "
                    "Use exact column names from the dataset. "
                    "Never invent column names or results. "
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
    """
    Validate Qwen's tool call and execute an approved Python tool.
    """

    function_name = tool_call["function"]["name"]
    arguments = tool_call["function"]["arguments"]

    if function_name != "aggregate_data":
        raise ValueError(
            f"Unsupported tool: {function_name}"
        )

    group_column = arguments.get("group_column")
    target_column = arguments.get("target_column")
    operation = arguments.get("operation")

    if group_column not in df.columns:
        raise ValueError("Invalid group column.")

    if target_column not in df.columns:
        raise ValueError("Invalid target column.")

    allowed_operations = [
        "mean",
        "sum",
        "min",
        "max",
        "count"
    ]

    if operation not in allowed_operations:
        raise ValueError("Invalid aggregation operation.")

    if operation in ["mean", "sum", "min", "max"]:
        if not pd.api.types.is_numeric_dtype(df[target_column]):
            raise ValueError(
                "Target column must be numerical."
            )

    result_df = aggregate_data(
        df,
        group_column=group_column,
        target_column=target_column,
        operation=operation
    )

    return result_df


# --------------------------------------------------
# MAIN DATASET ANALYSIS FUNCTION
# --------------------------------------------------

def analyze_dataset(df, question):
    """
    Complete AI agent workflow:

    1. Create tools dynamically.
    2. Ask Qwen to select a tool.
    3. Validate the tool call.
    4. Execute Python analysis.
    5. Return structured results.
    """

    if df.empty:
        raise ValueError("Cannot analyze an empty dataset.")

    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    tools = create_tools(df)

    message = ask_qwen(
        df,
        question,
        tools
    )

    tool_calls = message.get("tool_calls", [])

    if not tool_calls:
        raise ValueError(
            "The AI could not select an analysis tool "
            "for this question."
        )

    # This version supports one tool call per question.
    if len(tool_calls) != 1:
        raise ValueError(
            "Multiple tool calls are not supported yet."
        )

    tool_call = tool_calls[0]

    result_df = execute_tool(
        df,
        tool_call
    )

    return {
        "question": question,
        "selected_tool": tool_call["function"]["name"],
        "arguments": tool_call["function"]["arguments"],
        "results": result_df.to_dict(orient="records")
    }
