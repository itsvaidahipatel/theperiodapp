"""English (default) UI strings."""

from __future__ import annotations

from typing import Dict

STRINGS: Dict[str, str] = {
    # Confidence reasons
    "confidence.no_cycle_data": (
        "No cycle data available. Log at least 3 cycles for accurate predictions."
    ),
    "confidence.insufficient_data": (
        "Insufficient data. Log at least 3 cycles for better predictions."
    ),
    "confidence.log_3_cycles_count": (
        "Log at least 3 cycles for better predictions. Currently have {cycle_count} cycle(s)."
    ),
    "confidence.high_variance": (
        "High cycle variance (irregular cycles) reduces prediction confidence. "
        "Ovulation timing is less certain. More consistent logging will improve accuracy."
    ),
    "confidence.moderate_variance_count": (
        "Cycle variance is moderate; predictions are less certain. "
        "Based on {cycle_count} cycle(s)."
    ),
    "confidence.irregular_cv": (
        "Cycles are irregular (variance: {cv}%). More data will improve accuracy."
    ),
    "confidence.somewhat_irregular": (
        "Cycles are somewhat irregular. Tracking more cycles will improve accuracy."
    ),
    "confidence.good_regularity_count": (
        "Based on {cycle_count} cycle(s) with good regularity."
    ),
    "confidence.unable": "Unable to calculate confidence. Please log more periods.",
    "confidence.highly_irregular": (
        "Your recent cycle lengths vary by a very wide margin (more than a week). "
        "Predictions are unreliable until patterns stabilize; keep logging and discuss persistent "
        "irregularity with a clinician if concerned."
    ),
    # Stats insights
    "insight.log_3_cycles_more": (
        "Log at least 3 cycles for more accurate predictions and insights."
    ),
    "insight.regularity.irregular": (
        "Your cycles show high variability. Consider consulting a healthcare provider "
        "if this pattern continues."
    ),
    "insight.regularity.somewhat_irregular": (
        "Your cycles show moderate variability. Continue tracking to identify patterns."
    ),
    "insight.regularity.regular": "Your cycles are regular. Great job tracking!",
    "insight.regularity.very_regular": "Your cycles are very regular. Excellent consistency!",
    "insight.anomalies_count": (
        "You have {anomaly_count} cycle(s) outside the normal range (21-45 days)."
    ),
    "insight.period_short": (
        "Your period length ({period_days} days) is shorter than typical (3-8 days). "
        "This is detected from your logged data."
    ),
    "insight.period_long": (
        "Your period length ({period_days} days) is longer than typical (3-8 days). "
        "This is detected from your logged data."
    ),
    "insight.avg_cycle_short": (
        "Your average cycle length is shorter than typical. "
        "Consider discussing with a healthcare provider."
    ),
    "insight.avg_cycle_long": (
        "Your average cycle length is longer than typical. "
        "Consider discussing with a healthcare provider."
    ),
    "insight.continue_tracking": "Continue tracking your periods for personalized insights.",
    "insight.trend_detected": (
        "Your last 3 logged cycles are trending {trend} by more than 3 days at each step. "
        "If this continues, consider discussing with a healthcare provider."
    ),
    "insight.pcos_pattern": (
        "Your cycle variability is high. This can sometimes be associated with patterns like "
        "PCOS. Tracking more cycles or sharing this data with a doctor may be helpful."
    ),
    # Wellness phase advice (AI / wellness agents)
    "advice.menstrual": (
        "During menstruation, rest and gentle movement often feel best. Iron-rich foods and "
        "hydration may support how you feel; listen to your body."
    ),
    "advice.follicular": (
        "Energy often rises in the follicular phase. This can be a good time for new goals and "
        "moderate-to-higher intensity activity if it feels right for you."
    ),
    "advice.ovulatory": (
        "Around ovulation, some people feel peak energy or social drive. Balance activity "
        "with recovery and stay hydrated."
    ),
    "advice.luteal": (
        "In the luteal phase, you may prefer steadier routines, warmth, and lighter activity. "
        "Prioritize sleep and stress care if you notice PMS-type changes."
    ),
}
