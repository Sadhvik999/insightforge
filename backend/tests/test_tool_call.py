
import requests
import pandas as pd

from app.tools import aggregate_data


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5:1.5b"


df = pd.DataFrame({
    "City": ["Delhi", "Mumbai", "Delhi", "Mumbai", "Chennai"],
    "Sales": [500, 700, 300, 900, 400]
})


tools = [
    {
        "type": "function",
        "function": {
            "name": "aggregate_data",
            "description": (
                "Calculate aggregations on a dataset. "
                "Use this tool whenever the user asks for "
                "grouped calculations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "group_column": {
                        "type": "string",
                        "enum": ["City"]
                    },
                    "target_column": {
                        "type": "string",
                        "enum": ["Sales"]
                    },
                    "operation": {
                        "type": "string",
                        "enum": ["mean", "sum", "min", "max", "count"]
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


def test_tool_call():

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an AI data analyst. "
                    "You must use the aggregate_data tool "
                    "to perform grouped calculations. "
                    "Do not explain or describe the tool. "
                    "Call the tool directly."
                )
            },
            {
                "role": "user",
                "content": (
                    "Calculate the total sales for each city. "
                    "Use the aggregate_data tool now."
                )
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

    result = response.json()
    message = result["message"]

    print("\nQwen response:")
    print(message)

    tool_calls = message.get("tool_calls", [])

    if not tool_calls:
        print("\nQwen did not select a tool.")
        return

    for tool_call in tool_calls:

        function_name = tool_call["function"]["name"]
        arguments = tool_call["function"]["arguments"]

        print("\nFunction selected:", function_name)
        print("Arguments:", arguments)

        if function_name != "aggregate_data":
            print("Unknown function. Execution stopped.")
            return

        group_column = arguments["group_column"]
        target_column = arguments["target_column"]
        operation = arguments["operation"]

        if group_column not in df.columns:
            print("Invalid group column.")
            return

        if target_column not in df.columns:
            print("Invalid target column.")
            return

        if operation not in ["mean", "sum", "min", "max", "count"]:
            print("Invalid operation.")
            return

        result_df = aggregate_data(
            df,
            group_column=group_column,
            target_column=target_column,
            operation=operation
        )

        print("\nActual Python calculation:")
        print(result_df)


if __name__ == "__main__":
    test_tool_call()
