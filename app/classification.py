"""
Arsenic risk classification.

This is the decision layer that turns a raw arsenic concentration (µg/L)
into a human-readable water safety verdict, using WHO / Indian BIS 10500
reference points as the thresholds:

    WHO provisional guideline value           : 10 µg/L
    Indian BIS 10500 permissible (no alt src) : 50 µg/L
    Hazardous / acute-risk zone               : > 150 µg/L

The function is intentionally isolated from the API and DB layers so you
can later swap the fixed thresholds for a trained ML model (e.g. a
classifier that also weighs pH / conductivity / turbidity) without
touching anything else in the codebase — just change what happens
inside `classify_arsenic()` and keep the same return shape.
"""

from dataclasses import dataclass


@dataclass
class ClassificationResult:
    label: str          # Safe | Caution | Unsafe | Hazardous
    severity: int        # 0 (best) - 3 (worst), handy for sorting/UI colour
    message: str          # human-readable summary for the dashboard / robot display
    action: str          # recommended next step


# (upper_bound_ug_per_L, label, severity, message, action)
_THRESHOLDS = [
    (10.0, "Safe", 0,
     "Arsenic level is within the WHO provisional guideline (≤10 µg/L).",
     "No action needed. Continue routine monitoring."),
    (50.0, "Caution", 1,
     "Arsenic level exceeds the WHO guideline but is within India's BIS "
     "permissible limit (10–50 µg/L) where no alternate source exists.",
     "Flag for re-testing and consider filtration before consumption."),
    (150.0, "Unsafe", 2,
     "Arsenic level exceeds safe drinking limits (50–150 µg/L).",
     "Water is not safe to drink untreated. Recommend lab confirmation "
     "and alert local authority."),
    (float("inf"), "Hazardous", 3,
     "Arsenic level is critically high (>150 µg/L).",
     "Do not use this water source. Immediate lab confirmation and "
     "public health alert recommended."),
]


def classify_arsenic(arsenic_ppb: float) -> ClassificationResult:
    """
    Classify an arsenic concentration (µg/L, i.e. ppb) into a safety tier.

    Raises ValueError on physically impossible input (negative concentration).
    """
    if arsenic_ppb is None:
        raise ValueError("arsenic_ppb is required")
    if arsenic_ppb < 0:
        raise ValueError("arsenic_ppb cannot be negative")

    for upper_bound, label, severity, message, action in _THRESHOLDS:
        if arsenic_ppb <= upper_bound:
            return ClassificationResult(
                label=label, severity=severity, message=message, action=action
            )

    # Unreachable because the last threshold is +inf, but keeps type checkers happy.
    raise RuntimeError("classification fell through thresholds unexpectedly")
