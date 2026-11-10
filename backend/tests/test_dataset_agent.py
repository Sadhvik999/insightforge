
import requests
import pandas as pd

from pathlib import Path
from app.tools import aggregate_data


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5:1.5b"

DATASET_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "Sample - Superstore.csv"
)


# --------------------------------------------------
# LOAD REAL DATASET
# --------------------------------------------------

def load_dataset():

    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATASET_PATH}"
        )

    df = pd.read_csv(DATASET_PATH, encoding="latin1")

    if df.empty:
        raise ValueError("The uploaded dataset is empty.")

    return df


# --------------------------------------------------
# CREATE DYNAMIC TOOL DEFINITION
# --------------------------------------------------

def create_tools(df):

    all_columns = df.columns.tolist()

    numerical_columns = df.select_dtypes(
        include="number"
    ).columns.tolist()

    if not all_columns or not numerical_columns:
        raise ValueError(
            "Dataset must contain columns and at least one numerical column."
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
                            "enum": all_columns,
                            "description": "Column used for grouping."
                        },
                        "target_column": {
                            "type": "string",
                            "enum": numerical_columns,
                            "description": "Numerical column to analyze."
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
                    "Use the exact column names from the dataset. "
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

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=120
    )

    response.raise_for_status()

    return response.json()["message"]


# --------------------------------------------------
# EXECUTE APPROVED TOOL
# --------------------------------------------------

def execute_tool(df, tool_call):

    function_name = tool_call["function"]["name"]
    arguments = tool_call["function"]["arguments"]

    if function_name != "aggregate_data":
        raise ValueError(
            f"Unsupported tool: {function_name}"
        )

    group_column = arguments["group_column"]
    target_column = arguments["target_column"]
    operation = arguments["operation"]

    # Validate model-generated arguments

    if group_column not in df.columns:
        raise ValueError("Invalid group column.")

    if target_column not in df.columns:
        raise ValueError("Invalid target column.")

    if operation not in ["mean", "sum", "min", "max", "count"]:
        raise ValueError("Invalid aggregation operation.")

    if operation in ["mean", "sum", "min", "max"]:
        if not pd.api.types.is_numeric_dtype(df[target_column]):
            raise ValueError("Target column must be numerical.")

    # Execute existing Python analysis function

    result_df = aggregate_data(
        df,
        group_column=group_column,
        target_column=target_column,
        operation=operation
    )

    return result_df


# --------------------------------------------------
# MAIN AGENT WORKFLOW
# --------------------------------------------------

def main():

    print("\nLoading dataset...")

    df = load_dataset()

    print("Dataset loaded successfully!")

    print("\nDataset shape:", df.shape)

    print("\nAvailable columns:")
    print(df.columns.tolist())

    # User question

    question = (
        "Which region has the highest average sales? "
        "Calculate the average sales for each region."
    )

    print("\nUser question:")
    print(question)

    # Create dynamic tool definition

    tools = create_tools(df)

    # Ask Qwen to select a tool

    print("\nAsking Qwen to select a tool...")

    message = ask_qwen(df, question, tools)

    print("\nQwen response:")
    print(message)

    tool_calls = message.get("tool_calls", [])

    if not tool_calls:
        raise RuntimeError(
            "Qwen did not select a tool."
        )

    # Execute selected tool

    for tool_call in tool_calls:

        print("\nExecuting selected Python tool...")

        result_df = execute_tool(df, tool_call)

        print("\nAnalysis results:")
        print(result_df)

        # Identify the region with the highest average sales

        best_index = result_df["result"].idxmax()

        best_region = result_df.loc[
            best_index,
            tool_call["function"]["arguments"]["group_column"]
        ]

        best_average = result_df.loc[
            best_index,
            "result"
        ]

        print("\nFinal Answer:")
        print(
            f"{best_region} has the highest average sales "
            f"at {best_average:.2f}."
        )


if __name__ == "__main__":
    main()
