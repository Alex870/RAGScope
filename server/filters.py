from __future__ import annotations

import pandas as pd


def metadata_columns(frame: pd.DataFrame) -> list[str]:
    return sorted([column for column in frame.columns if column.startswith("meta.")])


def apply_text_filter(frame: pd.DataFrame, query: str) -> pd.DataFrame:
    if not query.strip() or frame.empty:
        return frame
    needle = query.casefold()
    mask = (
        frame["document"].fillna("").astype(str).str.casefold().str.contains(needle, regex=False)
        | frame["id"].fillna("").astype(str).str.casefold().str.contains(needle, regex=False)
        | frame["source"].fillna("").astype(str).str.casefold().str.contains(needle, regex=False)
        | frame["title"].fillna("").astype(str).str.casefold().str.contains(needle, regex=False)
    )
    return frame[mask]


def apply_metadata_filters(frame: pd.DataFrame, active_filters: dict) -> pd.DataFrame:
    result = frame
    for column, value in active_filters.items():
        if column not in result.columns:
            continue
        if isinstance(value, list) and len(value) == 2 and is_date_like(result[column].dropna()):
            dates = parse_dates(result[column])
            start = parse_dates(pd.Series([value[0]])).iloc[0]
            end = parse_dates(pd.Series([value[1]])).iloc[0]
            result = result[(dates >= start) & (dates <= end)]
        elif isinstance(value, list) and len(value) == 2 and pd.api.types.is_numeric_dtype(result[column].dropna()):
            result = result[(result[column] >= value[0]) & (result[column] <= value[1])]
        elif isinstance(value, list):
            if value:
                result = result[result[column].astype(str).isin(value)]
    return result


def is_date_like(values: pd.Series) -> bool:
    if values.empty:
        return False
    if pd.api.types.is_numeric_dtype(values):
        return False
    sample = values.astype(str).head(25)
    parsed = parse_dates(sample)
    return parsed.notna().mean() > 0.8


def parse_dates(values: pd.Series) -> pd.Series:
    try:
        return pd.to_datetime(values, errors="coerce", format="mixed")
    except TypeError:
        return pd.to_datetime(values, errors="coerce")
