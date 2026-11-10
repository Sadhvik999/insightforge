
import pandas as pd
import pytest

from app.tools import (
    get_column_info,
    get_dataset_summary,
    filter_data,
    aggregate_data
)


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "Name": ["Rahul", "Priya", "Amit", "Sneha", None],
        "Age": [21, 22, 21, 24, 23],
        "Salary": [30000, 40000, 35000, 50000, 45000],
        "City": ["Delhi", "Mumbai", "Delhi", "Chennai", "Mumbai"]
    })


# --------------------------------------------------
# Tests for get_column_info()
# --------------------------------------------------

def test_get_column_info(sample_df):
    result = get_column_info(sample_df)

    assert "Age" in result
    assert result["Age"]["is_numeric"] is True
    assert result["Name"]["is_numeric"] is False
    assert result["Name"]["missing_values"] == 1
    assert result["Age"]["unique_values"] == 4


# --------------------------------------------------
# Tests for get_dataset_summary()
# --------------------------------------------------

def test_get_dataset_summary(sample_df):
    result = get_dataset_summary(sample_df)

    assert result["total_rows"] == 5
    assert result["total_columns"] == 4
    assert result["numerical_columns_count"] == 2
    assert result["categorical_columns_count"] == 2
    assert result["total_missing_values"] == 1
    assert result["total_duplicate_rows"] == 0
    assert "Age" in result["numerical_columns"]


# --------------------------------------------------
# Tests for filter_data()
# --------------------------------------------------

def test_filter_data_greater_than(sample_df):
    result = filter_data(
        sample_df, "Salary", "gt", 35000
    )

    assert len(result) == 3
    assert (result["Salary"] > 35000).all()


def test_filter_data_equal(sample_df):
    result = filter_data(
        sample_df, "City", "eq", "Delhi"
    )

    assert len(result) == 2
    assert (result["City"] == "Delhi").all()


def test_filter_data_contains(sample_df):
    result = filter_data(
        sample_df, "Name", "contains", "a"
    )

    assert len(result) == 4


def test_filter_data_in(sample_df):
    result = filter_data(
        sample_df, "City", "in", ["Delhi", "Chennai"]
    )

    assert len(result) == 3


def test_filter_data_is_null(sample_df):
    result = filter_data(
        sample_df, "Name", "is_null"
    )

    assert len(result) == 1


def test_filter_data_not_null(sample_df):
    result = filter_data(
        sample_df, "Name", "not_null"
    )

    assert len(result) == 4


def test_filter_data_invalid_column(sample_df):
    with pytest.raises(ValueError):
        filter_data(sample_df, "Invalid", "eq", 10)


def test_filter_data_invalid_operator(sample_df):
    with pytest.raises(ValueError):
        filter_data(sample_df, "Age", "invalid", 10)


# --------------------------------------------------
# Tests for aggregate_data()
# --------------------------------------------------

def test_aggregate_data_mean(sample_df):
    result = aggregate_data(
        sample_df, "City", "Salary", "mean"
    )

    assert len(result) == 3

    delhi_mean = result.loc[
        result["City"] == "Delhi", "result"
    ].iloc[0]

    assert delhi_mean == 32500


def test_aggregate_data_sum(sample_df):
    result = aggregate_data(
        sample_df, "City", "Salary", "sum"
    )

    delhi_sum = result.loc[
        result["City"] == "Delhi", "result"
    ].iloc[0]

    assert delhi_sum == 65000


def test_aggregate_data_invalid_column(sample_df):
    with pytest.raises(ValueError):
        aggregate_data(
            sample_df, "Invalid", "Salary", "mean"
        )


def test_aggregate_data_invalid_operation(sample_df):
    with pytest.raises(ValueError):
        aggregate_data(
            sample_df, "City", "Salary", "median"
        )


def test_aggregate_data_non_numeric_mean(sample_df):
    with pytest.raises(ValueError):
        aggregate_data(
            sample_df, "City", "Name", "mean"
        )
