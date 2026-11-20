import json
import re
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
VISUALIZATION_WORDS = (
    r"\b(chart|charts|plot|plots|scatterplot|scatterplots|graph|graphs|"
    r"histogram|histograms|visualize|visualization|visualizations|"
    r"visualise|visualisation|visualisations)\b"
)
VISUALIZATION_PATTERN = re.compile(VISUALIZATION_WORDS, re.IGNORECASE)
NEGATION_PATTERN = re.compile(
    r"\b(don'?t|do not|never|no|without|skip|avoid)\b[^,.?!;]*" + VISUALIZATION_WORDS,
    re.IGNORECASE
)
EXISTING_VIZ_PATTERN = re.compile(
    r"\b(explain|describe|interpret|summarize|clarify|understand|walk through|tell me about|what does|what do)\b[^.?!;]*"
    r"\b(the|this|that|these|those|previous|last|earlier|above|existing|prior|created)?\s*"
    + VISUALIZATION_WORDS,
    re.IGNORECASE
)
INSTRUCTIONAL_PATTERN = re.compile(
    r"\b(how\s+(?:to|do|can|would|should)|(?:explain|describe|tell\s+me|show\s+me)\s+how)\b[^.?!;]*"
    r"\b(create|make|draw|generate|build|plot|visualize|visualise|chart)\b",
    re.IGNORECASE
)
CREATION_PATTERN = re.compile(
    r"\b(create|make|draw|generate|build)\b[^.?!;,]*" + VISUALIZATION_WORDS
    + r"|\b(show|display)\b[^.?!;,]*\b(as|in)\b[^.?!;,]*" + VISUALIZATION_WORDS
    + r"|(?<!\bthe\s)(?<!\bthis\s)(?<!\bthat\s)(?<!\ba\s)(?<!\ban\s)\b(show|display)\b\s+(me\s+|us\s+)?(a\s+|an\s+|the\s+)?([A-Za-z0-9_-]+\s+)?" + VISUALIZATION_WORDS
    + r"|(?<!\bthe\s)(?<!\bthis\s)(?<!\bthat\s)(?<!\ba\s)(?<!\ban\s)(?<!\bmy\s)(?<!\byour\s)(?<!\bour\s)(?<!\bprevious\s)(?<!\blast\s)(?<!\bearlier\s)(?<!\bprior\s)\b(plot|visualize|visualise|chart)\s+(?!above\b|below\b|again\b|here\b|is\b|was\b|are\b|were\b|looks\b|seems\b|shows\b|has\b|had\b)[A-Za-z0-9_]+",
    re.IGNORECASE
)
ANALYTICAL_COMMAND_PATTERN = re.compile(
    r"\b(calculate|compute|find|determine)\b[^.?!;]*\b(average|mean|sum|total|median|min|minimum|max|maximum|count|correlation|summary|statistics|metrics|table)\b|"
    r"\bwhat (is|are) the\b[^.?!;]*\b(average|mean|sum|total|median|min|max|count|correlation|summary|numbers)\b",
    re.IGNORECASE
)
def is_conversational_query(question):
    """
    Check if a question is an ordinary conversational greeting or pleasantry
    rather than an analytical or visualization request.
    """
    if not isinstance(question, str):
        return False
    return question.strip().lower().rstrip("!?.") in CONVERSATIONAL_GREETINGS
def is_visualization_query(question):
    """
    Check if a question explicitly requests creating a chart, plot, graph, or visualization.
    Excludes questions that negate visualization (e.g. "Don't create a chart"),
    refer to existing visualizations without asking for a new one (e.g. "Explain the previous chart"),
    or ask instructional questions (e.g. "Explain how to create a chart").
    Requires explicit creation intent rather than the mere presence of a visualization keyword.
    """
    if not isinstance(question, str):
        return False

    if not VISUALIZATION_PATTERN.search(question):
        return False

    if INSTRUCTIONAL_PATTERN.search(question):
        return False

    if EXISTING_VIZ_PATTERN.search(question) and not CREATION_PATTERN.search(question):
        return False

    cleaned = NEGATION_PATTERN.sub("", question)

    if not VISUALIZATION_PATTERN.search(cleaned):
        return False

    return bool(CREATION_PATTERN.search(cleaned))
def is_compound_query(question):
    """
    Check if a question requests both an analytical/numerical calculation
    and a visualization (e.g. "Calculate average Profit by Category and create a bar chart").
    """
    if not isinstance(question, str):
        return False

    if not is_visualization_query(question):
        return False

    return bool(ANALYTICAL_COMMAND_PATTERN.search(question))
def is_valid_visualization_result(result):
    """
    Validate that a visualization result or figure dictionary represents
    a valid Plotly figure with a non-empty data list containing valid trace dictionaries.
    """
    if not isinstance(result, dict):
        return False

    if "figure" in result:
        figure = result.get("figure")
    elif "data" in result:
        figure = result
    else:
        return False

    if not isinstance(figure, dict) or not figure:
        return False

    data = figure.get("data")
    if not isinstance(data, list) or not data:
        return False

    return all(isinstance(trace, dict) and bool(trace) for trace in data)
def has_valid_visualization(tool_results):
    """
    Check whether tool_results contains at least one valid visualization.
    """
    if not isinstance(tool_results, list):
        return False

    return any(
        isinstance(result, dict)
        and result.get("tool") == "visualize_data"
        and (
            is_valid_visualization_result(result.get("results"))
            or is_valid_visualization_result(result.get("result"))
        )
        for result in tool_results
    )
def is_plotly_figure(val, parent=None):
    """
    Check whether a value represents a Plotly figure payload
    (either valid or failed/empty) as opposed to an unrelated field named 'figure'.
    """
    if is_valid_visualization_result({"figure": val}):
        return True

    if isinstance(val, dict):
        if "data" in val or "layout" in val or "frames" in val:
            return True
        if isinstance(parent, dict) and ("chart_type" in parent or parent.get("tool") == "visualize_data"):
            return True

    if val is None and isinstance(parent, dict) and ("chart_type" in parent or parent.get("tool") == "visualize_data"):
        return True

    return False
def _sanitize_recursive(item):
    """
    Recursively remove raw Plotly figure dictionaries from dictionaries and lists.
    When a 'figure' key is found and its value is a Plotly figure, chart_status is
    added to its parent dictionary and the figure payload is removed.
    Preserves unrelated fields named 'figure' whose values are not Plotly figure objects.
    Preserves unrelated data and does not mutate the original input.
    """
    if isinstance(item, dict):
        has_fig_key = "figure" in item
        is_plotly = has_fig_key and is_plotly_figure(item["figure"], item)
        valid_figure = is_valid_visualization_result({"figure": item["figure"]}) if is_plotly else False

        new_dict = {}
        for k, v in item.items():
            if k == "figure" and is_plotly:
                continue
            new_dict[k] = _sanitize_recursive(v)

        if is_plotly:
            new_dict["chart_status"] = (
                "Visualization generated successfully."
                if valid_figure
                else "Visualization generation failed."
            )
        return new_dict
    elif isinstance(item, list):
        return [_sanitize_recursive(elem) for elem in item]
    else:
        return item
def sanitize_tool_payload(content):
    """
    Remove raw Plotly figures before passing tool output to the LLM.
    Recursively processes dictionaries and lists.
    Add chart_status at the appropriate parent level when a figure is found.
    Only report success when the figure is valid.
    Preserves unrelated data and does not mutate the original input.
    """
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return content

        if isinstance(parsed, (dict, list)):
            sanitized = _sanitize_recursive(parsed)
            return json.dumps(sanitized, default=str)
        return content

    if isinstance(content, (dict, list)):
        sanitized = _sanitize_recursive(content)
        return json.dumps(sanitized, default=str)

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
            "For visualization requests, you MUST call the visualize_data tool. "
            "visualize_data performs category aggregations (mean, sum, min, max, count) "
            "directly via its aggregation parameter. "
            "When the user explicitly asks for both numerical analysis/calculation and a chart "
            "(e.g. calculate values and create a chart), you MUST execute the appropriate "
            "analytical tool and also call visualize_data. "
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


    # Intent-aware tool selection
    visualization_requested = is_visualization_query(question)
    compound_requested = is_compound_query(question)

    if visualization_requested and not compound_requested:
        active_tools = [
            tool for tool in tools
            if tool.get("function", {}).get("name") == "visualize_data"
        ]
    else:
        active_tools = tools

    # Fallback if the visualization tool is unavailable
    if not active_tools:
        active_tools = tools
    while tool_count < max_tool_calls:
        message = ask_manager(
            messages,
            active_tools
        )
        tool_calls = message.get("tool_calls", [])
        if not tool_calls:
            # Check if this is a zero-tool text response for an analytical/visualization request
            if active_tools and tool_count == 0 and not is_conversational_query(question):
                if retries < max_retries:
                    retries += 1
                    messages.append(message)
                    if compound_requested:
                        nudge_content = (
                            "You have not executed any tool yet. You MUST execute the appropriate "
                            "analysis tool to perform the calculation and also call visualize_data "
                            "to generate the chart. Execute the tools now."
                        )
                    elif visualization_requested:
                        nudge_content = (
                            "You have not executed any tool yet. You MUST call visualize_data "
                            "to generate the requested chart. Execute visualize_data now."
                        )
                    else:
                        nudge_content = (
                            "You have not executed any tool yet. You MUST execute an available "
                            "Python tool to answer this question or generate this chart. "
                            "Execute the appropriate tool now."
                        )
                    messages.append({
                        "role": "user",
                        "content": nudge_content
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
                    if function_name == "visualize_data" and not is_valid_visualization_result(result):
                        tool_output = {
                            "success": False,
                            "error": "Visualization failed: figure was missing or empty."
                        }
                    else:
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
            llm_tool_output = _sanitize_recursive(tool_output)
            if function_name == "aggregate_data" and isinstance(tool_output.get("result"), list):
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
    viz_executed = has_valid_visualization(tool_results)
    if limit_reached:
        stop_reason = "max_tool_calls_reached"
    elif tool_count == 0 and active_tools and not is_conversational_query(question):
        stop_reason = "zero_tools_executed"
    elif is_visualization_query(question) and not viz_executed:
        stop_reason = "visualization_failed"
        final_message = "The requested visualization could not be generated."
        if messages and messages[-1].get("role") == "assistant":
            messages[-1]["content"] = final_message
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
