"""WIZZLE: Adversarial epistemic testing framework for autonomous modifiers.

WIZZLE is not a benchmark. It is an instrument for determining whether
an autonomous software modification system (like Ghost) is justified
in the semantic conclusions it draws from historical evidence.

Core model:
- Observation: What happened (verifiable)
- Interpretation: What it means (subjective)
- Conclusion: What Ghost concluded (may exceed entitlement)
- Entitlement: What evidence justifies what conclusion (explicit)

WIZZLE judges not whether Ghost finds bugs, but whether Ghost's
conclusions are semantically sound given the evidence available.
"""

__version__ = "2.0.0"
