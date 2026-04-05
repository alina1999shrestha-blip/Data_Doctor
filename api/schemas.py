"""Pydantic schemas for structured agent outputs."""

from pydantic import BaseModel, Field
from typing import Optional


# ── Profiler Agent Schemas ──────────────────────────────────────────

class ColumnProfile(BaseModel):
    name: str
    dtype: str
    semantic_type: str = Field(description="Inferred type: numeric, categorical, datetime, text, id, boolean")
    missing_count: int
    missing_pct: float
    unique_count: int
    sample_values: list[str]
    mean: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None
    min_val: Optional[str] = None
    max_val: Optional[str] = None
    skewness: Optional[float] = None


class ProfileReport(BaseModel):
    row_count: int
    col_count: int
    duplicate_rows: int
    memory_usage_mb: float
    columns: list[ColumnProfile]


# ── Anomaly Agent Schemas ───────────────────────────────────────────

class Anomaly(BaseModel):
    column: str
    anomaly_type: str = Field(description="One of: outlier, impossible_value, class_imbalance, high_correlation, constant_column, duplicate_column")
    severity: str = Field(description="One of: critical, warning, info")
    description: str
    affected_rows: Optional[int] = None
    recommendation: str


class AnomalyReport(BaseModel):
    total_anomalies: int
    critical_count: int
    warning_count: int
    info_count: int
    anomalies: list[Anomaly]


# ── Feature Engineer Agent Schemas ──────────────────────────────────

class FeatureSuggestion(BaseModel):
    column: str
    suggestion_type: str = Field(description="One of: encoding, scaling, transformation, interaction, decomposition, binning, extraction")
    description: str
    code_snippet: str = Field(description="Python pandas code to implement")
    impact: str = Field(description="One of: high, medium, low")
    rationale: str


class FeatureReport(BaseModel):
    total_suggestions: int
    high_impact_count: int
    suggestions: list[FeatureSuggestion]


# ── Supervisor / Final Report ───────────────────────────────────────

class HealthScore(BaseModel):
    overall_grade: str = Field(description="Letter grade A through F")
    overall_score: int = Field(description="Numeric score 0-100")
    completeness_score: int
    consistency_score: int
    outlier_score: int
    feature_readiness_score: int
    summary: str
    top_priorities: list[str]


class FullReport(BaseModel):
    health: HealthScore
    profile: ProfileReport
    anomalies: AnomalyReport
    features: FeatureReport


# ── Chat Schemas ────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    session_id: str
