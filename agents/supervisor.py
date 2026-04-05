"""Supervisor Agent — Scores data health and generates LLM-powered insights."""

import json
import os
from openai import OpenAI
from api.schemas import (
    ProfileReport, AnomalyReport, FeatureReport,
    HealthScore, FullReport,
)


def _compute_health_score(profile: ProfileReport, anomalies: AnomalyReport, features: FeatureReport) -> dict:
    """Compute numeric health sub-scores."""

    # Completeness (100 = no missing data)
    if profile.row_count == 0:
        completeness = 0
    else:
        total_cells = profile.row_count * profile.col_count
        total_missing = sum(c.missing_count for c in profile.columns)
        completeness = max(0, int(100 - (total_missing / max(total_cells, 1)) * 100))

    # Consistency (penalize anomalies)
    consistency = max(0, 100 - anomalies.critical_count * 20 - anomalies.warning_count * 8 - anomalies.info_count * 2)

    # Outlier score (100 = no outliers)
    outlier_anomalies = [a for a in anomalies.anomalies if a.anomaly_type == "outlier"]
    if outlier_anomalies and profile.row_count > 0:
        total_outlier_rows = sum(a.affected_rows or 0 for a in outlier_anomalies)
        outlier_pct = total_outlier_rows / profile.row_count * 100
        outlier_score = max(0, int(100 - outlier_pct * 3))
    else:
        outlier_score = 100

    # Feature readiness (bonus for high-impact suggestions already applicable)
    if features.total_suggestions == 0:
        feature_readiness = 85  # Already clean
    else:
        ratio = features.high_impact_count / max(features.total_suggestions, 1)
        feature_readiness = max(30, int(100 - ratio * 50))

    overall = int(completeness * 0.3 + consistency * 0.3 + outlier_score * 0.2 + feature_readiness * 0.2)

    if overall >= 90:
        grade = "A"
    elif overall >= 80:
        grade = "B"
    elif overall >= 65:
        grade = "C"
    elif overall >= 50:
        grade = "D"
    else:
        grade = "F"

    return {
        "overall_grade": grade,
        "overall_score": overall,
        "completeness_score": completeness,
        "consistency_score": consistency,
        "outlier_score": outlier_score,
        "feature_readiness_score": feature_readiness,
    }


def run_supervisor(
    profile: ProfileReport,
    anomalies: AnomalyReport,
    features: FeatureReport,
) -> FullReport:
    """Compile the full report with health scoring and LLM summary."""

    scores = _compute_health_score(profile, anomalies, features)

    # Build LLM prompt for the summary
    summary_prompt = f"""You are a senior data scientist reviewing a dataset quality report.

## Dataset Overview
- Rows: {profile.row_count}, Columns: {profile.col_count}
- Duplicate rows: {profile.duplicate_rows}
- Memory: {profile.memory_usage_mb} MB

## Column Types
{json.dumps([{"name": c.name, "type": c.semantic_type, "missing_pct": c.missing_pct} for c in profile.columns], indent=2)}

## Anomalies Found
- Critical: {anomalies.critical_count}, Warning: {anomalies.warning_count}, Info: {anomalies.info_count}
{json.dumps([{"column": a.column, "type": a.anomaly_type, "severity": a.severity, "description": a.description} for a in anomalies.anomalies], indent=2)}

## Feature Suggestions
- Total: {features.total_suggestions}, High impact: {features.high_impact_count}

## Health Scores
- Overall: {scores['overall_score']}/100 ({scores['overall_grade']})
- Completeness: {scores['completeness_score']}, Consistency: {scores['consistency_score']}
- Outlier: {scores['outlier_score']}, Feature readiness: {scores['feature_readiness_score']}

Write a 2-3 sentence executive summary of the dataset health. Then list the top 3-5 priority actions the user should take, ordered by impact. Be specific and reference actual column names.

Respond in JSON format:
{{"summary": "...", "top_priorities": ["action 1", "action 2", ...]}}
"""

    summary = "Dataset analysis complete."
    priorities = []

    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        summary = result.get("summary", summary)
        priorities = result.get("top_priorities", [])
    except Exception as e:
        # Fallback to rule-based summary if LLM fails
        summary = f"Dataset has {profile.row_count} rows and {profile.col_count} columns. Found {anomalies.total_anomalies} anomalies ({anomalies.critical_count} critical). Health grade: {scores['overall_grade']}."
        if anomalies.critical_count > 0:
            priorities.append("Address critical anomalies first")
        if any(c.missing_pct > 15 for c in profile.columns):
            priorities.append("Handle columns with high missing data")
        if features.high_impact_count > 0:
            priorities.append(f"Apply {features.high_impact_count} high-impact feature transformations")
        priorities.append("Review outlier columns before modeling")

    health = HealthScore(
        summary=summary,
        top_priorities=priorities[:5],
        **scores,
    )

    return FullReport(
        health=health,
        profile=profile,
        anomalies=anomalies,
        features=features,
    )
