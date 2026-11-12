
from app.response_generator import generate_aggregate_response
from app.response_generator import generate_multi_analysis_response

def test_aggregate_response_identifies_highest():
    arguments = {
        "group_column": "Region",
        "target_column": "Sales",
        "operation": "sum"
    }

    results = [
        {"Region": "Central", "result": 500},
        {"Region": "West", "result": 900},
        {"Region": "East", "result": 700}
    ]

    response = generate_aggregate_response(
        arguments,
        results
    )

    assert response["summary"] == (
        "West has the highest sum of Sales, at 900.00."
    )


def test_aggregate_response_identifies_lowest():
    arguments = {
        "group_column": "Region",
        "target_column": "Sales",
        "operation": "sum"
    }

    results = [
        {"Region": "Central", "result": 500},
        {"Region": "West", "result": 900},
        {"Region": "East", "result": 700}
    ]

    response = generate_aggregate_response(
        arguments,
        results
    )

    assert any(
        "Central has the lowest" in finding
        for finding in response["key_findings"]
    )


def test_aggregate_response_sorts_findings():
    arguments = {
        "group_column": "Region",
        "target_column": "Sales",
        "operation": "sum"
    }

    results = [
        {"Region": "Central", "result": 500},
        {"Region": "West", "result": 900},
        {"Region": "East", "result": 700}
    ]

    response = generate_aggregate_response(
        arguments,
        results
    )

    assert "West" in response["key_findings"][0]
    assert "East" in response["key_findings"][1]
    assert "Central" in response["key_findings"][2]


def test_aggregate_response_handles_empty_results():
    arguments = {
        "group_column": "Region",
        "target_column": "Sales",
        "operation": "sum"
    }

    response = generate_aggregate_response(
        arguments,
        []
    )

    assert response["summary"] == (
        "No aggregation results were available."
    )

    assert response["key_findings"] == []


def test_aggregate_response_handles_single_group():
    arguments = {
        "group_column": "Region",
        "target_column": "Sales",
        "operation": "sum"
    }

    results = [
        {"Region": "West", "result": 900}
    ]

    response = generate_aggregate_response(
        arguments,
        results
    )

    assert "West" in response["summary"]
    assert len(response["key_findings"]) == 1


def test_multi_analysis_with_multiple_aggregations():
    tool_results = [
        {
            "tool": "aggregate_data",
            "arguments": {
                "group_column": "City",
                "target_column": "Sales",
                "operation": "sum"
            },
            "results": [
                {"City": "Delhi", "result": 500},
                {"City": "Mumbai", "result": 800}
            ]
        },
        {
            "tool": "aggregate_data",
            "arguments": {
                "group_column": "City",
                "target_column": "Profit",
                "operation": "mean"
            },
            "results": [
                {"City": "Delhi", "result": 50},
                {"City": "Mumbai", "result": 100}
            ]
        }
    ]

    response = generate_multi_analysis_response(
        "Compare sales and profit by city.",
        tool_results
    )

    assert "Mumbai" in response["summary"]
    assert "Sales" in response["summary"]
    assert "Profit" in response["summary"]
    assert len(response["key_findings"]) >= 2


def test_multi_analysis_with_mixed_tools(monkeypatch):
    tool_results = [
        {
            "tool": "aggregate_data",
            "arguments": {
                "group_column": "City",
                "target_column": "Sales",
                "operation": "sum"
            },
            "results": [
                {"City": "Delhi", "result": 500},
                {"City": "Mumbai", "result": 800}
            ]
        },
        {
            "tool": "correlation_analysis",
            "arguments": {},
            "results": {
                "Sales": {
                    "Profit": 0.85
                }
            }
        }
    ]

    def fake_llm_response(question, evidence):
        return {
            "summary": "Sales and profit analysis completed.",
            "key_findings": [
                "The supplied evidence contains a correlation result."
            ]
        }

    monkeypatch.setattr(
        "app.response_generator._generate_llm_response",
        fake_llm_response
    )

    response = generate_multi_analysis_response(
        "Analyze sales and profit.",
        tool_results
    )

    assert response["summary"] == "Sales and profit analysis completed."
    assert any(
        "Mumbai" in finding
        for finding in response["key_findings"]
    )
    assert any(
        "correlation" in finding.lower()
        for finding in response["key_findings"]
    )


def test_multi_analysis_handles_empty_results():
    response = generate_multi_analysis_response(
        "Analyze the dataset.",
        []
    )

    assert response["summary"] == "No analysis results were available."
    assert response["key_findings"] == []
