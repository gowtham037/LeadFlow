"""
LeadFlow synthetic data generator.

Deterministic seed: 20261022 (matches InsureFlow convention).
Generates 20,000 leads + 10,000 contacts + 5,000 companies + 3,000 opportunities
plus all supporting records. Injects the 5 mandatory anomaly scenarios into
isolated records (is_baseline=False), preserving the baseline as 100% valid.

Ground truth is written to `data/ground_truth/ground_truth.csv` and is NEVER
used as scoring input — it exists only for evaluator benchmarking.

Usage (from repo root):
    python -m backend.app.data_generator --mode full --seed 20261022
    python -m backend.app.data_generator --mode starter
"""
__version__ = "0.1.0"
