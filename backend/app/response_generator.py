
import json
import requests


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5:1.5b"


def generate_aggregate_response(arguments, results):
    """
    Generate mathematically reliable explanations
    for aggregation results using Python.
    """

    if not isinstance(results, list) or not results:
        return {
            "summary": "No aggregation results were available.",
            "key_findings": []
        }

    group_column = arguments["group_column"]
    target_column = arguments["target_column"]
    operation = arguments["operation"]

    # Sort results using actual Python values.
    sorted_results = sorted(
        results,
        key=lambda item: (
            item["result"] is not None,
            item["result"] if item["result"] is not None else 0
        ),
        reverse=True
    )

    highest = sorted_results[0]
    lowest = sorted_results[-1]

    highest_group = highest[group_column]
    highest_value = highest["result"]

    lowest_group = lowest[group_column]
    lowest_value = lowest["result"]

    # Format values for human-readable output.
    def format_value(value):
        if isinstance(value, (int, float)):
            return f"{value:,.2f}"

        return str(value)

    summary = (
        f"{highest_group} has the highest "
        f"{operation} of {target_column}, "
        f"at {format_value(highest_value)}."
    )

    key_findings = [
        (
            f"{item[group_column]} has a "
            f"{operation} of {target_column} equal to "
            f"{format_value(item['result'])}."
        )
        for item in sorted_results[:3]
    ]

    if len(sorted_results) > 1:
        key_findings.append(
            f"{lowest_group} has the lowest "
            f"{operation} of {target_column}, "
            f"at {format_value(lowest_value)}."
        )

    return {
        "summary": summary,
        "key_findings": key_findings
    }


def generate_analysis_response(
    question,
    selected_tool,
    arguments,
    results
):
    """
    Generate a human-readable analysis response.

    Python performs calculations and rankings.
    Qwen explains non-aggregation results.
    """

    # Aggregation rankings are calculated by Python.
    if selected_tool == "aggregate_data":
        return generate_aggregate_response(
            arguments,
            results
        )

    # Keep visualization data small.
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

    evidence_text = json.dumps(
        evidence,
        default=str
    )

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
                    "Each key finding must be a complete, informative sentence. "
                    "Include relevant columns and values when available. "
                    "Do not include Markdown or extra text."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n"
                    f"Selected tool: {selected_tool}\n"
                    f"Tool arguments: {json.dumps(arguments, default=str)}\n"
                    f"Actual Python results: {evidence_text}"
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
            raise ValueError(
                "Invalid summary generated by AI."
            )

        if not isinstance(key_findings, list):
            raise ValueError(
                "Invalid key findings generated by AI."
            )

        if not all(
            isinstance(item, str)
            for item in key_findings
        ):
            raise ValueError(
                "Key findings must contain strings."
            )

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
