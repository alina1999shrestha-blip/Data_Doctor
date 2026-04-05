"""Visualization Generator — Creates Plotly chart configs from analysis results."""

import pandas as pd
import numpy as np
import json
from api.schemas import FullReport


def generate_visualizations(df: pd.DataFrame, report: FullReport) -> list[dict]:
    """Generate a list of Plotly chart configurations."""
    charts = []

    # 1. Missing values heatmap
    missing_data = []
    for col_prof in report.profile.columns:
        if col_prof.missing_pct > 0:
            missing_data.append({"column": col_prof.name, "missing_pct": col_prof.missing_pct})

    if missing_data:
        missing_df = sorted(missing_data, key=lambda x: x["missing_pct"], reverse=True)[:15]
        charts.append({
            "id": "missing_values",
            "title": "Missing values by column",
            "type": "bar",
            "data": [{
                "x": [d["column"] for d in missing_df],
                "y": [d["missing_pct"] for d in missing_df],
                "type": "bar",
                "marker": {
                    "color": [
                        "#E24B4A" if d["missing_pct"] > 50
                        else "#EF9F27" if d["missing_pct"] > 15
                        else "#1D9E75"
                        for d in missing_df
                    ]
                },
            }],
            "layout": {
                "yaxis": {"title": "Missing %"},
                "xaxis": {"tickangle": -35},
                "margin": {"b": 100},
            }
        })

    # 2. Distribution histograms for numeric columns
    numeric_cols = [c for c in report.profile.columns if c.semantic_type == "numeric"]
    for col_prof in numeric_cols[:6]:  # Max 6 histograms
        series = df[col_prof.name].dropna()
        if len(series) == 0:
            continue

        charts.append({
            "id": f"dist_{col_prof.name}",
            "title": f"Distribution: {col_prof.name}",
            "type": "histogram",
            "data": [{
                "x": series.tolist()[:5000],  # Cap at 5000 points
                "type": "histogram",
                "nbinsx": 30,
                "marker": {"color": "#534AB7", "opacity": 0.75},
            }],
            "layout": {
                "xaxis": {"title": col_prof.name},
                "yaxis": {"title": "Count"},
                "annotations": [{
                    "x": 0.98, "y": 0.95,
                    "xref": "paper", "yref": "paper",
                    "text": f"μ={col_prof.mean} | σ={col_prof.std} | skew={col_prof.skewness}",
                    "showarrow": False,
                    "font": {"size": 11, "color": "#666"},
                }] if col_prof.mean is not None else [],
            }
        })

    # 3. Correlation matrix for numeric columns
    numeric_col_names = [c.name for c in numeric_cols]
    if len(numeric_col_names) >= 2:
        corr = df[numeric_col_names[:12]].corr()  # Max 12 columns
        charts.append({
            "id": "correlation_matrix",
            "title": "Correlation matrix",
            "type": "heatmap",
            "data": [{
                "z": corr.values.round(2).tolist(),
                "x": corr.columns.tolist(),
                "y": corr.index.tolist(),
                "type": "heatmap",
                "colorscale": "RdBu_r",
                "zmin": -1, "zmax": 1,
                "text": corr.values.round(2).tolist(),
                "texttemplate": "%{text}",
                "textfont": {"size": 10},
            }],
            "layout": {
                "xaxis": {"tickangle": -35},
                "margin": {"b": 100, "l": 100},
            }
        })

    # 4. Anomaly severity breakdown
    if report.anomalies.total_anomalies > 0:
        charts.append({
            "id": "anomaly_breakdown",
            "title": "Anomaly severity breakdown",
            "type": "pie",
            "data": [{
                "values": [
                    report.anomalies.critical_count,
                    report.anomalies.warning_count,
                    report.anomalies.info_count,
                ],
                "labels": ["Critical", "Warning", "Info"],
                "type": "pie",
                "marker": {"colors": ["#E24B4A", "#EF9F27", "#1D9E75"]},
                "hole": 0.4,
                "textinfo": "label+value",
            }],
            "layout": {}
        })

    # 5. Top categorical value counts
    cat_cols = [c for c in report.profile.columns if c.semantic_type == "categorical" and c.unique_count <= 15]
    for col_prof in cat_cols[:3]:
        vc = df[col_prof.name].value_counts().head(10)
        charts.append({
            "id": f"cat_{col_prof.name}",
            "title": f"Value counts: {col_prof.name}",
            "type": "bar",
            "data": [{
                "x": vc.index.astype(str).tolist(),
                "y": vc.values.tolist(),
                "type": "bar",
                "marker": {"color": "#0F6E56"},
            }],
            "layout": {
                "xaxis": {"tickangle": -35, "title": col_prof.name},
                "yaxis": {"title": "Count"},
                "margin": {"b": 100},
            }
        })

    # 6. Health score radar
    charts.append({
        "id": "health_radar",
        "title": "Health score breakdown",
        "type": "radar",
        "data": [{
            "type": "scatterpolar",
            "r": [
                report.health.completeness_score,
                report.health.consistency_score,
                report.health.outlier_score,
                report.health.feature_readiness_score,
                report.health.completeness_score,  # close the polygon
            ],
            "theta": ["Completeness", "Consistency", "Outliers", "Feature readiness", "Completeness"],
            "fill": "toself",
            "fillcolor": "rgba(83,74,183,0.15)",
            "line": {"color": "#534AB7"},
        }],
        "layout": {
            "polar": {
                "radialaxis": {"visible": True, "range": [0, 100]},
            },
        }
    })

    return charts
