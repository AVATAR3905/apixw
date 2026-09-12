"""Unified database seed entry point (`make seed`, `python -m database.seeds.seed_all`).

Boots the complete observatory dataset: reference routes/airlines/sources/methodology,
DGCA route weights, 30 days of synthetic verification observations, daily indices,
MoSPI CPI benchmark series, and ATF fuel series.
"""

from services.seed_demo_data import run_full_seed_pipeline

if __name__ == "__main__":
    run_full_seed_pipeline()
