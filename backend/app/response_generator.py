
import json
import requests


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5:1.5b"


def generate_aggregate_response(arguments, results, question=None):
    """
    Generate mathematically reliable explanations
    for aggregation results using Python.

    Supports both highest and lowest questions.
    """

    if not isinstance(results, list) or not results:
        return {
            "summary": "No aggregation results were available.",
            "key_findings": []
        }

    group_column = arguments["group_column"]
    target_column = arguments["target_column"]
    operation = arguments["operation"]

    # Determine whether the user wants the highest or lowest.
    question_text = (question or "").lower()

    lowest_keywords = [
        "lowest",
        "least",
        "minimum",
        "smallest",
        "fewest"
    ]

    highest_keywords = [
        "highest",
        "most",
        "maximum",
        "largest",
        "greatest"
    ]

    wants_lowest = any(
        keyword in question_text
        for keyword in lowest_keywords
    )

    wants_highest = any(
        keyword in question_text
        for keyword in highest_keywords
    )

    # Default to highest to preserve previous behavior.
    if wants_lowest and not wants_highest:
        ranking = "lowest"
    else:
        ranking = "highest"

    # Ignore null aggregation results while ranking.
    valid_results = [
        item for item in results
        if item.get("result") is not None
    ]

    if not valid_results:
        return {
            "summary": "No valid aggregation values were available.",
            "key_findings": []
        }

    sorted_results = sorted(
        valid_results,
        key=lambda item: item["result"],
        reverse=(ranking == "highest")
    )

    selected = sorted_results[0]

    selected_group = selected[group_column]
    selected_value = selected["result"]

    highest = max(
        valid_results,
        key=lambda item: item["result"]
    )

    lowest = min(
        valid_results,
        key=lambda item: item["result"]
    )

    def format_value(value):
        if isinstance(value, (int, float)):
            return f"{value:,.2f}"

        return str(value)

    summary = (
        f"{selected_group} has the {ranking} "
        f"{operation} of {target_column}, "
        f"at {format_value(selected_value)}."
    )

    key_findings = [
        (
            f"{item[group_column]} has a "
            f"{operation} of {target_column} equal to "
            f"{format_value(item['result'])}."
        )
        for item in sorted_results[:3]
    ]

    # Include the opposite extreme when there is more than one group.
    if len(valid_results) > 1:

        opposite = lowest if ranking == "highest" else highest

        opposite_ranking = (
            "lowest" if ranking == "highest" else "highest"
        )

        key_findings.append(
            f"{opposite[group_column]} has the {opposite_ranking} "
            f"{operation} of {target_column}, "
            f"at {format_value(opposite['result'])}."
        )

    return {
        "summary": summary,
        "key_findings": key_findings
    }


def _generate_llm_response(question, evidence):
    """
    Ask the local Qwen model to explain supplied evidence.
    Python remains responsible for actual calculations.
    """

    evidence_text = json.dumps(evidence, default=str)

    max_evidence_length = 12000

    if len(evidence_text) > max_evidence_length:
        evidence_text = (
            evidence_text[:max_evidence_length]
            + "\n[Results truncated for explanation.]"
        )

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an AI data analyst. "
                    "Explain the supplied Python analysis results. "
                    "Do not calculate new statistics. "
                    "Do not invent values, columns, or findings. "
                    "Use only facts supported by the evidence. "
                    "If evidence is insufficient, say so. "
                    "Return valid JSON with exactly two keys: "
                    "summary and key_findings. "
                    "summary must be a short string. "
                    "key_findings must be a list of strings. "
                    "Each key finding must be a complete sentence. "
                    "Do not include Markdown or extra text."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n"
                    f"Actual Python evidence: {evidence_text}"
                )
            }
        ],
        "stream": False,
        "format": "json",
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

        content = response.json()["message"]["content"]
        explanation = json.loads(content)

        summary = explanation.get("summary")
        key_findings = explanation.get("key_findings")

        if not isinstance(summary, str):
            raise ValueError("Invalid summary generated by AI.")

        if not isinstance(key_findings, list):
            raise ValueError("Invalid key findings generated by AI.")

        if not all(isinstance(item, str) for item in key_findings):
            raise ValueError("Key findings must contain strings.")

        return {
            "summary": summary,
            "key_findings": key_findings
        }

    except requests.exceptions.RequestException as e:
        raise RuntimeError(
            f"Could not generate AI explanation: {e}"
        )

    except (KeyError, json.JSONDecodeError, ValueError) as e:
        raise RuntimeError(
            f"Invalid AI explanation response: {e}"
        )


def generate_analysis_response(
    question,
    selected_tool,
    arguments,
    results
):
    """
    Generate a human-readable response for one tool.
    """

    if selected_tool == "aggregate_data":
        return generate_aggregate_response(
            arguments,
            results,
            question
        )

    if selected_tool == "visualize_data":
        evidence = {
            "chart_type": results.get("chart_type"),
            "x_column": results.get("x_column"),
            "y_column": results.get("y_column"),
            "title": results.get("title"),
            "note": "A chart was successfully generated."
        }
    else:
        evidence = results

    return _generate_llm_response(
        question,
        {
            "selected_tool": selected_tool,
            "arguments": arguments,
            "results": evidence
        }
    )


def generate_multi_analysis_response(
    question,
    tool_results,
    final_message=None
):
    """
    Generate one response from multiple tool executions.

    Aggregation calculations and rankings are generated
    deterministically using Python.
    """

    if not isinstance(tool_results, list) or not tool_results:
        return {
            "summary": "No analysis results were available.",
            "key_findings": []
        }

    evidence = []
    deterministic_findings = []
    aggregation_summaries = []
    aggregation_count = 0

    for item in tool_results:
        tool_name = item.get("tool")
        arguments = item.get("arguments", {})
        results = item.get("results")

        if tool_name == "aggregate_data":
            aggregation_count += 1

            aggregation_response = generate_aggregate_response(
                arguments,
                results,
                question
            )

            aggregation_summaries.append(
                aggregation_response["summary"]
            )

            deterministic_findings.extend(
                aggregation_response["key_findings"]
            )

            evidence.append({
                "tool": tool_name,
                "arguments": arguments,
                "python_generated_findings": aggregation_response
            })

        elif tool_name == "visualize_data":
            evidence.append({
                "tool": tool_name,
                "chart_type": results.get("chart_type"),
                "x_column": results.get("x_column"),
                "y_column": results.get("y_column"),
                "title": results.get("title"),
                "note": "A chart was successfully generated."
            })

        else:
            evidence.append({
                "tool": tool_name,
                "arguments": arguments,
                "results": results
            })

    # If every tool performed aggregation, use Python only.
    if aggregation_count == len(tool_results):
        return {
            "summary": " ".join(aggregation_summaries),
            "key_findings": deterministic_findings
        }

    # For mixed tool results, ask Qwen to explain the evidence.
    if final_message:
        evidence.append({
            "manager_analysis": final_message
        })

    ai_response = _generate_llm_response(
        question,
        evidence
    )

    # Add Python-generated aggregation findings.
    ai_response["key_findings"].extend(
        deterministic_findings
    )

    return ai_response
