"""Feature Engineer Agent — Suggests transformations and encodings."""

import pandas as pd
import numpy as np
from api.schemas import FeatureSuggestion, FeatureReport, ProfileReport


def run_feature_engineer(df: pd.DataFrame, profile: ProfileReport) -> FeatureReport:
    """Generate feature engineering suggestions based on profiling results."""
    suggestions: list[FeatureSuggestion] = []

    for col_prof in profile.columns:
        col = col_prof.name

        # Skip ID columns
        if col_prof.semantic_type == "id":
            continue

        # ── Numeric column suggestions ────────────────────────────
        if col_prof.semantic_type == "numeric":

            # Skewness → log transform
            if col_prof.skewness is not None and abs(col_prof.skewness) > 1.5:
                direction = "right" if col_prof.skewness > 0 else "left"
                suggestions.append(FeatureSuggestion(
                    column=col,
                    suggestion_type="transformation",
                    description=f"Apply log transform to reduce {direction}-skewness ({col_prof.skewness})",
                    code_snippet=f"df['{col}_log'] = np.log1p(df['{col}'].clip(lower=0))",
                    impact="high",
                    rationale=f"Skewness of {col_prof.skewness} indicates a heavy tail. Log transform can normalize the distribution and improve model performance for linear models.",
                ))

            # High range → scaling
            if col_prof.min_val is not None and col_prof.max_val is not None:
                try:
                    range_val = float(col_prof.max_val) - float(col_prof.min_val)
                    if range_val > 1000:
                        suggestions.append(FeatureSuggestion(
                            column=col,
                            suggestion_type="scaling",
                            description=f"Standardize or min-max scale (range: {round(range_val, 1)})",
                            code_snippet=f"from sklearn.preprocessing import StandardScaler\ndf['{col}_scaled'] = StandardScaler().fit_transform(df[['{col}']])",
                            impact="medium",
                            rationale="Large value ranges can dominate distance-based models (KNN, SVM) and slow gradient descent convergence.",
                        ))
                except (ValueError, TypeError):
                    pass

            # Binning suggestion for continuous with many unique values
            if col_prof.unique_count > 100:
                suggestions.append(FeatureSuggestion(
                    column=col,
                    suggestion_type="binning",
                    description="Create bins/quantiles for tree-based interpretability",
                    code_snippet=f"df['{col}_binned'] = pd.qcut(df['{col}'], q=5, labels=['very_low','low','mid','high','very_high'], duplicates='drop')",
                    impact="low",
                    rationale="Discretizing continuous features can help with interpretability and capture non-linear relationships in simple models.",
                ))

        # ── Categorical column suggestions ────────────────────────
        elif col_prof.semantic_type == "categorical":

            if col_prof.unique_count <= 10:
                suggestions.append(FeatureSuggestion(
                    column=col,
                    suggestion_type="encoding",
                    description=f"One-hot encode ({col_prof.unique_count} categories)",
                    code_snippet=f"df = pd.get_dummies(df, columns=['{col}'], prefix='{col}')",
                    impact="high",
                    rationale=f"Low cardinality ({col_prof.unique_count} unique values) — one-hot encoding is safe and won't cause dimensionality issues.",
                ))
            elif col_prof.unique_count <= 50:
                suggestions.append(FeatureSuggestion(
                    column=col,
                    suggestion_type="encoding",
                    description=f"Target encode ({col_prof.unique_count} categories — too many for one-hot)",
                    code_snippet=f"# Target encoding (replace 'target' with your actual target column)\nmeans = df.groupby('{col}')['target'].mean()\ndf['{col}_encoded'] = df['{col}'].map(means)",
                    impact="high",
                    rationale=f"Medium cardinality ({col_prof.unique_count}) — one-hot would add too many columns. Target encoding preserves information compactly.",
                ))
            else:
                suggestions.append(FeatureSuggestion(
                    column=col,
                    suggestion_type="encoding",
                    description=f"Hash encode or embed ({col_prof.unique_count} unique values)",
                    code_snippet=f"# Hash encoding with 8 components\nimport category_encoders as ce\nencoder = ce.HashingEncoder(cols=['{col}'], n_components=8)\ndf = encoder.fit_transform(df)",
                    impact="medium",
                    rationale=f"High cardinality ({col_prof.unique_count}) — hash encoding keeps dimensionality fixed.",
                ))

        # ── Datetime suggestions ──────────────────────────────────
        elif col_prof.semantic_type == "datetime":
            suggestions.append(FeatureSuggestion(
                column=col,
                suggestion_type="decomposition",
                description="Extract datetime components (year, month, day_of_week, hour)",
                code_snippet=f"df['{col}'] = pd.to_datetime(df['{col}'])\ndf['{col}_year'] = df['{col}'].dt.year\ndf['{col}_month'] = df['{col}'].dt.month\ndf['{col}_dow'] = df['{col}'].dt.dayofweek\ndf['{col}_hour'] = df['{col}'].dt.hour",
                impact="high",
                rationale="Raw datetime is unusable by most models. Decomposing captures cyclical patterns (weekday effects, seasonality).",
            ))

            suggestions.append(FeatureSuggestion(
                column=col,
                suggestion_type="transformation",
                description="Create cyclical encoding for month and day_of_week",
                code_snippet=f"df['{col}_month_sin'] = np.sin(2 * np.pi * df['{col}'].dt.month / 12)\ndf['{col}_month_cos'] = np.cos(2 * np.pi * df['{col}'].dt.month / 12)",
                impact="medium",
                rationale="Cyclical encoding prevents models from treating December and January as far apart.",
            ))

        # ── Text column suggestions ───────────────────────────────
        elif col_prof.semantic_type == "text":
            suggestions.append(FeatureSuggestion(
                column=col,
                suggestion_type="extraction",
                description="Extract text length and word count as features",
                code_snippet=f"df['{col}_length'] = df['{col}'].str.len()\ndf['{col}_word_count'] = df['{col}'].str.split().str.len()",
                impact="medium",
                rationale="Text length and word count often correlate with target variables and are easy wins.",
            ))

        # ── Boolean suggestions ───────────────────────────────────
        elif col_prof.semantic_type == "boolean":
            suggestions.append(FeatureSuggestion(
                column=col,
                suggestion_type="encoding",
                description="Map to binary 0/1",
                code_snippet=f"df['{col}'] = df['{col}'].map({{True: 1, False: 0, 'yes': 1, 'no': 0, 'Y': 1, 'N': 0}}).fillna(0).astype(int)",
                impact="low",
                rationale="Ensures consistent numeric representation for model consumption.",
            ))

    # ── Missing value imputation suggestions ──────────────────────
    for col_prof in profile.columns:
        if col_prof.missing_pct > 5 and col_prof.missing_pct <= 50:
            if col_prof.semantic_type == "numeric":
                suggestions.append(FeatureSuggestion(
                    column=col_prof.name,
                    suggestion_type="transformation",
                    description=f"Create missing indicator + median imputation ({col_prof.missing_pct}% missing)",
                    code_snippet=f"df['{col_prof.name}_missing'] = df['{col_prof.name}'].isna().astype(int)\ndf['{col_prof.name}'] = df['{col_prof.name}'].fillna(df['{col_prof.name}'].median())",
                    impact="high",
                    rationale="The missingness pattern itself may be informative. A missing indicator captures this signal.",
                ))

    high_impact = sum(1 for s in suggestions if s.impact == "high")

    return FeatureReport(
        total_suggestions=len(suggestions),
        high_impact_count=high_impact,
        suggestions=suggestions,
    )
