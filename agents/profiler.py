"""Profiler Agent — Analyzes CSV structure, types, and distributions."""

import pandas as pd
import numpy as np
from api.schemas import ColumnProfile, ProfileReport


def run_profiler(df: pd.DataFrame) -> ProfileReport:
    """Profile every column in the dataframe."""

    columns = []

    for col in df.columns:
        series = df[col]
        dtype_str = str(series.dtype)
        missing = int(series.isna().sum())
        missing_pct = round(missing / len(df) * 100, 2) if len(df) > 0 else 0.0
        unique = int(series.nunique())

        # Sample values (up to 5, dropping NaN)
        samples = series.dropna().head(5).astype(str).tolist()

        # Infer semantic type
        semantic = _infer_semantic_type(series, dtype_str, unique, len(df))

        # Numeric stats
        mean = median = std = skewness = None
        min_val = max_val = None

        if pd.api.types.is_numeric_dtype(series):
            clean = series.dropna()
            if len(clean) > 0:
                mean = round(float(clean.mean()), 4)
                median = round(float(clean.median()), 4)
                std = round(float(clean.std()), 4)
                min_val = str(clean.min())
                max_val = str(clean.max())
                skewness = round(float(clean.skew()), 4)
        else:
            non_null = series.dropna()
            if len(non_null) > 0:
                min_val = str(non_null.min())
                max_val = str(non_null.max())

        columns.append(ColumnProfile(
            name=col,
            dtype=dtype_str,
            semantic_type=semantic,
            missing_count=missing,
            missing_pct=missing_pct,
            unique_count=unique,
            sample_values=samples,
            mean=mean,
            median=median,
            std=std,
            min_val=min_val,
            max_val=max_val,
            skewness=skewness,
        ))

    mem_mb = round(df.memory_usage(deep=True).sum() / (1024 * 1024), 2)

    return ProfileReport(
        row_count=len(df),
        col_count=len(df.columns),
        duplicate_rows=int(df.duplicated().sum()),
        memory_usage_mb=mem_mb,
        columns=columns,
    )


def _infer_semantic_type(series: pd.Series, dtype: str, unique: int, total: int) -> str:
    """Infer semantic type from column characteristics."""
    name = series.name.lower() if series.name else ""

    # ID detection
    if any(kw in name for kw in ["id", "_id", "uuid", "key"]):
        return "id"

    # Boolean detection
    if unique <= 2 and all(v in (0, 1, True, False, 'yes', 'no', 'true', 'false', 'Y', 'N') for v in series.dropna().unique()):
        return "boolean"

    # Datetime detection
    if "date" in dtype or "time" in dtype:
        return "datetime"
    if any(kw in name for kw in ["date", "time", "timestamp", "created", "updated"]):
        try:
            pd.to_datetime(series.dropna().head(20))
            return "datetime"
        except (ValueError, TypeError):
            pass

    # Numeric
    if pd.api.types.is_numeric_dtype(series):
        if unique <= 10:
            return "categorical"
        return "numeric"

    # Categorical vs text
    if unique / max(total, 1) < 0.3 or unique <= 50:
        return "categorical"

    # Check average string length for text detection
    avg_len = series.dropna().astype(str).str.len().mean()
    if avg_len > 50:
        return "text"

    return "categorical"
