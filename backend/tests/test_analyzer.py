
import pandas as pd
import pytest

from app.analyzer import (
    numerical_summary,
    categorical_summary,
    group_analysis,
    correlation_analysis
)


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "Category": ["A", "B", "A", "B"],
        "Sales": [100, 200, 150, 250],
        "Profit": [20, 40, 30, 50],
        "Quantity": [2, 4, 3, 5]
    })


def test_numerical_summary(sample_df):
    result = numerical_summary(sample_df)

    assert "Sales" in result.columns
    assert result.loc["mean", "Sales"] == 175


def test_categorical_summary(sample_df):
    result = categorical_summary(sample_df)

    assert result["Category"]["unique_values"] == 2
    assert result["Category"]["most_frequent"] in ["A", "B"]


def test_group_analysis(sample_df):
    result = group_analysis(
        sample_df, "Category", "Sales", "sum"
    )

    assert result["A"] == 250
    assert result["B"] == 450


def test_correlation_analysis(sample_df):
    result = correlation_analysis(
        sample_df, columns=["Sales", "Profit"]
    )

    assert result.shape == (2, 2)
    assert result.loc["Sales", "Sales"] == 1.0


def test_invalid_group_column(sample_df):
    with pytest.raises(ValueError):
        group_analysis(sample_df, "Invalid", "Sales", "sum")
