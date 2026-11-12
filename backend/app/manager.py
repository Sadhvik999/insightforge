
import json
import requests


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5:1.5b"

MAX_TOOL_CALLS = 5


def ask_manager(messages, tools):
    """Ask Qwen what to do next using conversation history."""

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
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
            f"Manager could not communicate with Ollama: {e}"
        )


def run_manager(
    df,
    question,
    tools,
    tool_executor,
    max_tool_calls=MAX_TOOL_CALLS
):
    """
    Coordinate multiple approved Python tool executions.
    """

    if (
        not isinstance(max_tool_calls, int)
        or isinstance(max_tool_calls, bool)
        or max_tool_calls < 1
    ):
        raise ValueError(
            "Maximum tool calls must be a positive integer."
        )

    messages = [
        {
            "role": "system",
            "content": (
                "You are the Manager Agent of an AI data analyst. "
                "Use available Python tools to answer questions. "
                "Identify every separate task requested by the user. "
                "Complete every requested task before providing a final answer. "
                "If the user requests both an overall dataset summary "
                "and column-level information, you MUST call "
                "get_dataset_summary and get_column_info. "
                "Execute one tool at a time and examine its result "
                "before deciding which tool to call next. "
                "Do not stop after completing only one part of a multi-part request. "
                "Use previous tool results to decide what to do next. "
                "Never invent columns or numerical results. "
                "Python tool results are the source of truth. "
                "Do not repeat identical tool calls. "
                "When enough evidence is collected, stop calling tools "
                "and provide a concise final answer. "
                "Never generate or execute Python code."
            )
        },
        {
            "role": "user",
            "content": question
        }
    ]

    tool_results = []
    executed_calls = set()

    tool_count = 0
    final_message = None
    limit_reached = False

    while tool_count < max_tool_calls:

        message = ask_manager(
            messages,
            tools
        )

        tool_calls = message.get("tool_calls", [])

        if not tool_calls:
            final_message = message.get("content", "")
            break

        # Preserve the assistant's tool-call message.
        messages.append(message)

        
        for tool_call in tool_calls:

            function = tool_call.get("function", {})
            function_name = function.get("name")
            arguments = function.get("arguments", {})

            if tool_count >= max_tool_calls:
                limit_reached = True
                break

            tool_count += 1

            if not isinstance(arguments, dict):
                raise ValueError("Invalid tool arguments.")

            call_signature = json.dumps(
                {
                    "tool": function_name,
                    "arguments": arguments
                },
                sort_keys=True,
                default=str
            )

            if call_signature in executed_calls:

                tool_output = {
                    "success": False,
                    "error": "Duplicate tool call rejected."
                }

            else:
                executed_calls.add(call_signature)

                try:
                    result = tool_executor(
                        df,
                        tool_call
                    )

                    tool_output = {
                        "success": True,
                        "result": result
                    }

                    tool_results.append({
                        "tool": function_name,
                        "arguments": arguments,
                        "results": result
                    })

                except (ValueError, TypeError, KeyError) as e:
                    tool_output = {
                        "success": False,
                        "error": str(e)
                    }

            messages.append({
                "role": "tool",
                "tool_name": function_name,
                "content": json.dumps(
                    tool_output,
                    default=str
                )
            })

        if limit_reached:
            break


    return {
        "tool_results": tool_results,
        "tool_calls_count": tool_count,
        "final_message": final_message,
        "stop_reason": (
            "completed"
            if final_message is not None
            else "max_tool_calls_reached"
        )
    }
