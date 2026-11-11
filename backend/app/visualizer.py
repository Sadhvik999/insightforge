
import pandas as pd
import plotly.express as px


def create_visualization(
    df,
    chart_type,
    x_column,
    y_column=None,
    title=None
):
    """
    Create a Plotly visualization dynamically.

    Supported chart types:
        bar, line, histogram, scatter
    """

    if df.empty:
        raise ValueError("Cannot visualize an empty dataset.")

    if x_column not in df.columns:
        raise ValueError(f"Column not found: {x_column}")

    if y_column is not None and y_column not in df.columns:
        raise ValueError(f"Column not found: {y_column}")

    if chart_type not in ["bar", "line", "histogram", "scatter"]:
        raise ValueError(f"Unsupported chart type: {chart_type}")

    if chart_type in ["bar", "line", "scatter"]:
        if y_column is None:
            raise ValueError(
                f"{chart_type} chart requires a y_column."
            )

    if chart_type == "bar":
        fig = px.bar(
            df,
            x=x_column,
            y=y_column,
            title=title or f"{y_column} by {x_column}"
        )

    elif chart_type == "line":
        fig = px.line(
            df,
            x=x_column,
            y=y_column,
            title=title or f"{y_column} over {x_column}",
            markers=True
        )

    elif chart_type == "histogram":
        fig = px.histogram(
            df,
            x=x_column,
            title=title or f"Distribution of {x_column}"
        )

    else:
        fig = px.scatter(
            df,
            x=x_column,
            y=y_column,
            title=title or f"{y_column} vs {x_column}"
        )

    fig.update_layout(
        template="plotly_white",
        xaxis_title=x_column,
        yaxis_title=y_column or "Count"
    )

    return fig
