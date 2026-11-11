
from app.response_generator import generate_aggregate_response


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
