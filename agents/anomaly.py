"""Anomaly Detective Agent — Finds outliers, impossible values, and data quality issues."""

import pandas as pd
import numpy as np
from scipy import stats
from api.schemas import Anomaly, AnomalyReport, ProfileReport


def run_anomaly_detection(df: pd.DataFrame, profile: ProfileReport) -> AnomalyReport:
    """Detect anomalies across the dataset."""
    anomalies: list[Anomaly] = []

    # 1. Outlier detection (IQR method) for numeric columns
    for col_prof in profile.columns:
        if col_prof.semantic_type == "numeric" and col_prof.std is not None:
            series = df[col_prof.name].dropna()
            if len(series) < 10:
                continue

            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1

            if iqr > 0:
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                outlier_count = int(((series < lower) | (series > upper)).sum())

                if outlier_count > 0:
                    pct = round(outlier_count / len(series) * 100, 1)
                    severity = "critical" if pct > 10 else "warning" if pct > 3 else "info"
                    anomalies.append(Anomaly(
                        column=col_prof.name,
                        anomaly_type="outlier",
                        severity=severity,
                        description=f"{outlier_count} outliers ({pct}%) detected outside IQR bounds [{round(lower, 2)}, {round(upper, 2)}]",
                        affected_rows=outlier_count,
                        recommendation=f"Investigate outliers. Consider capping at [{round(lower, 2)}, {round(upper, 2)}] or using robust scaling.",
                    ))

    # 2. Impossible / suspicious values
    for col_prof in profile.columns:
        name_lower = col_prof.name.lower()
        if col_prof.semantic_type == "numeric" and col_prof.min_val is not None:
            min_v = float(col_prof.min_val)

            # Negative values in typically non-negative fields
            if any(kw in name_lower for kw in ["age", "price", "salary", "income", "count", "quantity", "weight", "height"]):
                neg_count = int((df[col_prof.name].dropna() < 0).sum())
                if neg_count > 0:
                    anomalies.append(Anomaly(
                        column=col_prof.name,
                        anomaly_type="impossible_value",
                        severity="critical",
                        description=f"{neg_count} negative values found in '{col_prof.name}' which typically should be non-negative",
                        affected_rows=neg_count,
                        recommendation="Review and correct negative values. These are likely data entry errors.",
                    ))

    # 3. Class imbalance detection for categorical columns
    for col_prof in profile.columns:
        if col_prof.semantic_type in ("categorical", "boolean") and col_prof.unique_count >= 2:
            value_counts = df[col_prof.name].value_counts(normalize=True)
            if len(value_counts) >= 2:
                max_ratio = value_counts.iloc[0]
                min_ratio = value_counts.iloc[-1]
                if max_ratio > 0.9:
                    anomalies.append(Anomaly(
                        column=col_prof.name,
                        anomaly_type="class_imbalance",
                        severity="warning",
                        description=f"Severe class imbalance: dominant class is {round(max_ratio * 100, 1)}% of values",
                        affected_rows=None,
                        recommendation="Consider SMOTE, undersampling, or class weights if this is a target variable.",
                    ))

    # 4. Constant / near-constant columns
    for col_prof in profile.columns:
        if col_prof.unique_count <= 1:
            anomalies.append(Anomaly(
                column=col_prof.name,
                anomaly_type="constant_column",
                severity="warning",
                description=f"Column has only {col_prof.unique_count} unique value(s) — provides no information",
                affected_rows=None,
                recommendation="Drop this column before modeling.",
            ))

    # 5. High missing data
    for col_prof in profile.columns:
        if col_prof.missing_pct > 50:
            anomalies.append(Anomaly(
                column=col_prof.name,
                anomaly_type="impossible_value",
                severity="critical",
                description=f"{col_prof.missing_pct}% missing values — majority of data is absent",
                affected_rows=col_prof.missing_count,
                recommendation="Consider dropping this column or investigating why data is missing (MCAR/MAR/MNAR).",
            ))
        elif col_prof.missing_pct > 15:
            anomalies.append(Anomaly(
                column=col_prof.name,
                anomaly_type="impossible_value",
                severity="warning",
                description=f"{col_prof.missing_pct}% missing values detected",
                affected_rows=col_prof.missing_count,
                recommendation="Use imputation (mean/median for numeric, mode for categorical) or build a missingness indicator.",
            ))

    # 6. High correlation detection (potential data leakage)
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if len(numeric_cols) >= 2:
        corr_matrix = df[numeric_cols].corr().abs()
        checked = set()
        for i, c1 in enumerate(numeric_cols):
            for j, c2 in enumerate(numeric_cols):
                if i >= j:
                    continue
                pair = tuple(sorted([c1, c2]))
                if pair in checked:
                    continue
                checked.add(pair)
                val = corr_matrix.loc[c1, c2]
                if val > 0.95:
                    anomalies.append(Anomaly(
                        column=f"{c1} ↔ {c2}",
                        anomaly_type="high_correlation",
                        severity="warning",
                        description=f"Correlation of {round(val, 3)} — possible data leakage or redundancy",
                        affected_rows=None,
                        recommendation="Drop one of these columns or investigate if one is derived from the other.",
                    ))

    # 7. Duplicate row detection
    if profile.duplicate_rows > 0:
        pct = round(profile.duplicate_rows / profile.row_count * 100, 1)
        anomalies.append(Anomaly(
            column="[all columns]",
            anomaly_type="duplicate_column",
            severity="warning" if pct > 5 else "info",
            description=f"{profile.duplicate_rows} duplicate rows ({pct}%) found",
            affected_rows=profile.duplicate_rows,
            recommendation="Remove duplicates with df.drop_duplicates() unless they are expected.",
        ))

    critical = sum(1 for a in anomalies if a.severity == "critical")
    warning = sum(1 for a in anomalies if a.severity == "warning")
    info = sum(1 for a in anomalies if a.severity == "info")

    return AnomalyReport(
        total_anomalies=len(anomalies),
        critical_count=critical,
        warning_count=warning,
        info_count=info,
        anomalies=anomalies,
    )
