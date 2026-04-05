"""Chat Agent — Conversational data exploration powered by OpenAI."""

import json
import os
from openai import OpenAI
from api.schemas import FullReport


# In-memory session store: session_id -> {"report": ..., "messages": [...]}
_sessions: dict = {}


def init_chat_session(session_id: str, report: FullReport, df_sample_json: str):
    """Initialize a chat session with the analysis context."""
    
    columns_info = json.dumps([
        {"name": c.name, "type": c.semantic_type, "missing": c.missing_pct, 
         "unique": c.unique_count, "mean": c.mean, "std": c.std, "skewness": c.skewness}
        for c in report.profile.columns
    ], indent=1)
    
    anomalies_info = json.dumps([
        {"column": a.column, "type": a.anomaly_type, "severity": a.severity, 
         "description": a.description, "recommendation": a.recommendation}
        for a in report.anomalies.anomalies
    ], indent=1)
    
    features_info = json.dumps([
        {"column": s.column, "type": s.suggestion_type, "description": s.description, 
         "code": s.code_snippet, "impact": s.impact}
        for s in report.features.suggestions
    ], indent=1)

    system_msg = f"""You are Data Doctor, an expert data scientist assistant. The user has uploaded a CSV file and you've completed a full quality analysis. Here are the results:

## Health Score: {report.health.overall_grade} ({report.health.overall_score}/100)
- Completeness: {report.health.completeness_score}/100
- Consistency: {report.health.consistency_score}/100
- Outlier score: {report.health.outlier_score}/100
- Feature readiness: {report.health.feature_readiness_score}/100

## Summary
{report.health.summary}

## Dataset Profile
- Rows: {report.profile.row_count}, Columns: {report.profile.col_count}
- Duplicate rows: {report.profile.duplicate_rows}

## Columns
{columns_info}

## Anomalies ({report.anomalies.total_anomalies} total)
{anomalies_info}

## Feature Suggestions ({report.features.total_suggestions} total)
{features_info}

## Sample Data (first 5 rows)
{df_sample_json}

Instructions:
- Answer questions about the dataset using the analysis results above.
- When asked "why" a column is flagged, explain the specific statistical reasoning.
- When suggesting fixes, provide executable Python/Pandas code snippets.
- If asked to generate a visualization, describe what chart would be most informative and provide Plotly code.
- Be concise but thorough. Use the user's column names exactly.
- If you don't have enough info to answer, say so honestly.
"""

    _sessions[session_id] = {
        "messages": [{"role": "system", "content": system_msg}],
    }


def chat(session_id: str, user_message: str) -> str:
    """Process a chat message and return the assistant's response."""
    if session_id not in _sessions:
        return "Session not found. Please upload a CSV first."

    session = _sessions[session_id]
    session["messages"].append({"role": "user", "content": user_message})

    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=session["messages"],
            temperature=0.4,
            max_tokens=1500,
        )
        reply = response.choices[0].message.content
    except Exception as e:
        reply = f"Error communicating with the LLM: {str(e)}. Please check your OPENAI_API_KEY."

    session["messages"].append({"role": "assistant", "content": reply})

    # Keep context window manageable (last 20 messages + system)
    if len(session["messages"]) > 22:
        session["messages"] = [session["messages"][0]] + session["messages"][-20:]

    return reply
