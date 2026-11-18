
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


CONVERSATIONAL_GREETINGS = {
    "hello", "hi", "hey", "greetings", "thanks", "thank you", "bye", "goodbye", "help"
}


def is_conversational_query(question):
    """
    Check if a question is an ordinary conversational greeting or pleasantry
    rather than an analytical or visualization request.
    """
    if not isinstance(question, str):
        return False
    return question.strip().lower().rstrip("!?.") in CONVERSATIONAL_GREETINGS


def sanitize_tool_payload(content):
    """
    Ensure tool output does not contain raw Plotly figure dictionaries
    or excessively large payloads before passing to LLM context.
    """
    parsed = None
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            parsed = None
    elif isinstance(content, dict):
        parsed = content.copy()

    if isinstance(parsed, dict):
        if "result" in parsed and isinstance(parsed["result"], dict):
            res = parsed["result"]
            if "figure" in res:
                sanitized_res = {k: v for k, v in res.items() if k != "figure"}
                sanitized_res["chart_status"] = (
                    "Visualization generated successfully."
                )
                parsed["result"] = sanitized_res
        elif "figure" in parsed:
            del parsed["figure"]
            parsed["chart_status"] = (
                "Visualization generated successfully."
            )

        return json.dumps(parsed, default=str)

    if isinstance(content, str):
        return content

    return json.dumps(content, default=str)


def prepare_conversation_history(conversation_history):
    """
    Format previous conversation messages for the LLM context.
    Preserves user messages, assistant tool calls, sanitized tool results,
    and final assistant messages to maintain valid tool-calling dialogue structure.
    """

    if not conversation_history:
        return []

    cleaned_history = []

    for message in conversation_history:
        if not isinstance(message, dict):
            continue

        role = message.get("role")
        content = message.get("content", "")

        if role == "user" and content:
            cleaned_history.append({
                "role": "user",
                "content": content
            })
        elif role == "assistant":
            tool_calls = message.get("tool_calls")
            if tool_calls:
                cleaned_history.append({
                    "role": "assistant",
                    "content": content or "",
                    "tool_calls": tool_calls
                })
            elif content:
                cleaned_history.append({
                    "role": "assistant",
                    "content": content
                })
        elif role == "tool":
            sanitized_content = sanitize_tool_payload(content)
            tool_entry = {
                "role": "tool",
                "content": sanitized_content
            }
            if "tool_name" in message:
                tool_entry["tool_name"] = message["tool_name"]
            cleaned_history.append(tool_entry)

    return cleaned_history


def run_manager(
    df,
    question,
    tools,
    tool_executor,
    max_tool_calls=MAX_TOOL_CALLS,
    conversation_history=None
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

    system_message = {
        "role": "system",
        "content": (
            "You are the Manager Agent of an AI data analyst. "

            "You MUST use an available Python tool for every "
            "new analytical question and every visualization, chart, or plot request, "
            "including all follow-up turns. Never answer an analysis or visualization "
            "request using only conversation history or text alone. "

            "For any chart, plot, or graph request (such as bar, line, scatter, or histogram), "
            "you MUST call the visualize_data tool. "

            "You are strictly prohibited from stating or claiming that a chart, plot, "
            "or calculation was created or completed unless the corresponding tool "
            "was actually executed during the current turn. "

            "Use previous conversation context to understand references "
            "such as 'it', 'that', or 'those'. "

            "Previous Python tool results are evidence, but you "
            "must execute a fresh tool call for the current question. "

            "Identify every separate task requested by the user. "
            "Complete every requested task before providing a final answer. "

            "If the user requests both an overall dataset summary "
            "and column-level information, you MUST call "
            "get_dataset_summary and get_column_info. "

            "Execute one tool at a time and examine its result "
            "before deciding which tool to call next. "

            "Do not stop after completing only one part of a "
            "multi-part request. "

            "Never invent columns or numerical results. "
            "Python tool results are the source of truth. "

            "Do not repeat identical tool calls within the current request. "

            "When enough evidence is collected, stop calling tools "
            "and provide a concise final answer. "

            "Never generate or execute Python code."
        )
    }

    previous_history = prepare_conversation_history(
        conversation_history
    )

    messages = [
        system_message,
        *previous_history,
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
    retries = 0
    max_retries = 1

    while tool_count < max_tool_calls:

        message = ask_manager(
            messages,
            tools
        )

        # TEMPORARY DEBUG OUTPUT
        print("\n========== MANAGER DEBUG ==========")
        print(json.dumps(message, indent=2))
        print("===================================\n")

        tool_calls = message.get("tool_calls", [])

        if not tool_calls:
            # Check if this is a zero-tool text response for an analytical/visualization request
            if tools and tool_count == 0 and not is_conversational_query(question):
                if retries < max_retries:
                    retries += 1
                    messages.append(message)
                    messages.append({
                        "role": "user",
                        "content": (
                            "You have not executed any tool yet. You MUST execute an available "
                            "Python tool to answer this question or generate this chart. "
                            "Execute the appropriate tool now."
                        )
                    })
                    continue

                # Retry limit reached without any tool executed
                messages.append(message)
                final_message = "The AI could not execute any valid analysis tools."
                break

            final_message = message.get("content", "")
            messages.append(message)
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

            llm_tool_output = tool_output
            if function_name == "visualize_data" and isinstance(tool_output.get("result"), dict):
                llm_result = {
                    k: v for k, v in tool_output["result"].items()
                    if k != "figure"
                }
                llm_result["chart_status"] = "Visualization generated successfully."
                llm_tool_output = {
                    "success": tool_output.get("success", True),
                    "result": llm_result
                }
            elif function_name == "aggregate_data" and isinstance(tool_output.get("result"), list):
                target_col = arguments.get("target_column")
                if target_col:
                    renamed_records = []
                    for row in tool_output["result"]:
                        if isinstance(row, dict) and "result" in row:
                            new_row = row.copy()
                            new_row[target_col] = new_row.pop("result")
                            renamed_records.append(new_row)
                        else:
                            renamed_records.append(row)
                    llm_tool_output = {
                        "success": tool_output.get("success", True),
                        "result": renamed_records
                    }

            messages.append({
                "role": "tool",
                "tool_name": function_name,
                "content": json.dumps(
                    llm_tool_output,
                    default=str
                )
            })

        if limit_reached:
            break

    if limit_reached:
        stop_reason = "max_tool_calls_reached"
    elif tool_count == 0 and tools and not is_conversational_query(question):
        stop_reason = "zero_tools_executed"
    elif final_message is not None:
        stop_reason = "completed"
    else:
        stop_reason = "max_tool_calls_reached"

    return {
        "tool_results": tool_results,
        "tool_calls_count": tool_count,
        "final_message": final_message,
        "stop_reason": stop_reason,
        "conversation_history": messages[1:]
    }
