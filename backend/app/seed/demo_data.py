"""Deterministic demo data generators (no network, no randomness at runtime).

Two datasets:
  1. Haryana district rainfall + wheat production 2020–2025 (the hero demo)
  2. India EV sales by manufacturer 2022–2025 (secondary demo)

Both include *planted* dirty rows (duplicates, entity variants, negative
values, '₹'-style strings) so the validation engine visibly catches real
problems during the demo.
"""
from __future__ import annotations

import csv
import zlib
from pathlib import Path


def _stable_hash(s: str) -> int:
    """Deterministic across runs/machines (unlike builtin hash)."""
    return zlib.crc32(s.encode("utf-8"))

DEMO_DIR = Path(__file__).parent / "demo_data"

# 10 Haryana districts with plausible long-term monsoon means (mm) and
# baseline wheat productivity (t per district-year), with a rain-yield link.
DISTRICTS: list[tuple[str, float, float]] = [
    ("Karnal", 720, 105000),
    ("Kaithal", 640, 92000),
    ("Kurukshetra", 700, 98000),
    ("Hisar", 480, 74000),
    ("Rohtak", 560, 80000),
    ("Sirsa", 430, 68000),
    ("Panipat", 610, 86000),
    ("Jind", 580, 83000),
    ("Ambala", 750, 101000),
    ("Bhiwani", 460, 62000),
]

# Per-year monsoon deviation multiplier (drought 2021/2022, good 2023/2025)
YEAR_RAINFACTOR: dict[int, float] = {2020: 0.95, 2021: 0.78, 2022: 0.88, 2023: 1.12, 2024: 0.98, 2025: 1.18}
# Yield response to rainfall deviation (elasticity), plus tech trend
YIELD_ELASTICITY = 0.45
TECH_TREND: dict[int, float] = {2020: 1.00, 2021: 1.02, 2022: 1.04, 2023: 1.07, 2024: 1.09, 2025: 1.12}

EV_MANUFACTURERS = ["Tata Motors", "MG Motor", "Mahindra", "Hyundai", "BYD India", "Ashok Leyland", "Ola Electric"]
EV_BASE: dict[str, int] = {
    "Tata Motors": 24000,
    "MG Motor": 8000,
    "Mahindra": 9500,
    "Hyundai": 6800,
    "BYD India": 1500,
    "Ashok Leyland": 3100,
    "Ola Electric": 4100,
}
EV_GROWTH: dict[str, float] = {  # annual growth multiplier
    "Tata Motors": 1.34,
    "MG Motor": 1.18,
    "Mahindra": 1.41,
    "Hyundai": 1.22,
    "BYD India": 1.55,
    "Ashok Leyland": 1.12,
    "Ola Electric": 1.28,
}


def _entity_variants(name: str) -> dict[str, int]:
    """Planted variants: 'Hisar', 'HISAR', 'hisar ' style duplicates of same entity."""
    return {
        name: 1,
        name.upper(): 1,
        name.lower() + " ": 1,
    }


def generate_rainfall_wheat() -> Path:
    """Rainfall + wheat production per district-year, 2020–2025, with dirty rows."""
    out = DEMO_DIR / "haryana_rainfall_wheat.csv"
    if out.exists():
        return out

    rows: list[list] = []
    for dname, rain_mean, prod_base in DISTRICTS:
        for year, rf in YEAR_RAINFACTOR.items():
            # rainfall deviates around district mean
            rain = round(rain_mean * rf * (1 + 0.05 * (_stable_hash(dname) % 9 - 4) / 8), 1)
            # production responds to rainfall (elasticity) + tech trend
            rain_dev = rain / rain_mean
            prod = round(prod_base * TECH_TREND[year] * (rain_dev ** YIELD_ELASTICITY))
            state = "Haryana"
            rows.append([dname, state, year, rain, prod])

    # --- Planted dirty rows (validation must catch these) ---
    dirty = [
        ["HISAR", "Haryana", 2024, 520.5, 80200],        # entity variant (uppercase)
        ["hisar ", "Haryana", 2024, 518.0, 79800],       # entity variant (lowercase+space)
        ["Kaithal", "Haryana", 2022, -45.0, 88000],      # invalid: negative rainfall
        ["Sirsa", "Haryana", 2021, "₹480 lakh", 66500],  # invalid: unit-mismatch string in numeric col
        ["Jind", "Haryana", 2024, 590.3, None],          # missing production
        ["", "Haryana", 2025, 500.0, 70000],             # missing district
    ]
    rows.extend(dirty)
    # duplicate two clean rows (duplicate detection)
    rows.append(list(rows[0]))
    rows.append(list(rows[15]))

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["district", "state", "year", "rainfall_mm", "wheat_production_t"])
        w.writerows(rows)
    return out


def generate_ev_sales() -> Path:
    """EV sales by manufacturer/year 2022–2025 with planted dirty rows."""
    out = DEMO_DIR / "india_ev_sales.csv"
    if out.exists():
        return out

    rows: list[list] = []
    for maker, base in EV_BASE.items():
        g = EV_GROWTH[maker]
        for i, year in enumerate([2022, 2023, 2024, 2025]):
            val = round(base * (g ** i))
            rows.append([maker, year, "India", val])

    dirty = [
        ["Tata Motors Inc.", 2025, "India", 58000],   # entity variant of Tata Motors
        ["tata motors", 2025, "India", 57400],        # lowercase variant
        ["Mahindra", 2024, "India", -800],            # invalid negative
        ["Hyundai", 2023, "India", "₹6.8k"],          # unit-mismatch string in numeric col
        ["BYD India", 2022, "India", None],           # missing value
    ]
    rows.extend(dirty)
    rows.append(list(rows[0]))  # duplicate

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["manufacturer", "year", "country", "sales_units"])
        w.writerows(rows)
    return out


SCHEMAS = {
    "haryana_rainfall_wheat.csv": {
        "columns": [
            {"name": "district", "type": "string"},
            {"name": "state", "type": "string"},
            {"name": "year", "type": "integer"},
            {"name": "rainfall_mm", "type": "float"},
            {"name": "wheat_production_t", "type": "float"},
        ],
    },
    "india_ev_sales.csv": {
        "columns": [
            {"name": "manufacturer", "type": "string"},
            {"name": "year", "type": "integer"},
            {"name": "country", "type": "string"},
            {"name": "sales_units", "type": "integer"},
        ],
    },
}
