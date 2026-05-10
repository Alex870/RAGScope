from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


DEFAULT_PALETTE = (
    px.colors.qualitative.Plotly
    + px.colors.qualitative.Dark24
    + px.colors.qualitative.Safe
)


def categorical_color_map(values: list[str]) -> dict[str, str]:
    clean_values = sorted({str(value) for value in values if str(value)})
    return {
        value: DEFAULT_PALETTE[index % len(DEFAULT_PALETTE)]
        for index, value in enumerate(clean_values)
    }


def scatter_plot(
    frame: pd.DataFrame,
    color_column: str,
    highlighted_ids: list[str],
    color_map: dict[str, str] | None = None,
    dimensions: int = 2,
    height: int = 680,
    dragmode: str = "pan",
    enable_hover: bool = True,
) -> go.Figure:
    if frame.empty:
        return go.Figure()

    color = color_column if color_column in frame.columns else "cluster"
    hover_columns = [
        column
        for column in ["id", "source", "title", "preview", "cluster", "topic_label"]
        if column in frame.columns
    ]
    chart_kwargs = {
        "data_frame": frame,
        "x": "x",
        "y": "y",
        "color": color,
        "hover_data": None,
        "custom_data": ["id", "preview"],
        "template": "plotly_dark",
        "height": height,
    }
    if color_map:
        chart_kwargs["color_discrete_map"] = color_map
    if dimensions == 3 and "z" in frame.columns:
        chart_kwargs["z"] = "z"
        fig = px.scatter_3d(**chart_kwargs)
    else:
        fig = px.scatter(**chart_kwargs)
    fig.update_traces(marker={"size": 8, "opacity": 0.78})
    if enable_hover:
        fig.update_traces(
            hovertemplate="<b>Preview</b><br>%{customdata[1]}<extra></extra>"
        )
    else:
        fig.update_traces(hoverinfo="skip", hovertemplate=None)

    if highlighted_ids:
        highlight = frame[frame["id"].astype(str).isin(set(highlighted_ids))]
        if not highlight.empty:
            if dimensions == 3 and "z" in frame.columns:
                fig.add_trace(
                    go.Scatter3d(
                        x=highlight["x"],
                        y=highlight["y"],
                        z=highlight["z"],
                        mode="markers",
                        marker={"size": 8, "color": "#ffdd57", "symbol": "circle-open", "line": {"color": "#ffdd57", "width": 3}},
                        hoverinfo="skip",
                        name="Highlighted",
                    )
                )
            else:
                fig.add_trace(
                    go.Scatter(
                        x=highlight["x"],
                        y=highlight["y"],
                        mode="markers",
                        marker={"size": 16, "color": "rgba(255, 255, 255, 0)", "line": {"color": "#ffdd57", "width": 3}},
                        hoverinfo="skip",
                        name="Highlighted",
                    )
                )

    fig.update_layout(
        margin={"l": 8, "r": 8, "t": 28, "b": 8},
        legend_title_text=color,
        dragmode=dragmode,
    )
    return fig
