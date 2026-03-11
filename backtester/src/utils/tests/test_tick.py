"""Tests for tick normalization — normalize_price (090)."""

import pytest

from src.utils.tick import normalize_price


def test_normalize_es_exact_tick() -> None:
    """5412.50 is already on tick boundary -> unchanged."""
    assert normalize_price(5412.50, 0.25) == 5412.50


def test_normalize_es_round_down() -> None:
    """5412.30 rounds to 5412.25 (nearest tick)."""
    assert normalize_price(5412.30, 0.25) == 5412.25


def test_normalize_es_half_even() -> None:
    """5412.375 exactly between ticks -> half-even rounds to 5412.50."""
    assert normalize_price(5412.375, 0.25) == 5412.50


def test_normalize_es_half_even_down() -> None:
    """5412.125 exactly between ticks -> half-even rounds to 5412.00."""
    assert normalize_price(5412.125, 0.25) == 5412.00


def test_normalize_cl_small_tick() -> None:
    """CL tick 0.01: 72.346 -> 72.35."""
    assert normalize_price(72.346, 0.01) == 72.35


def test_normalize_zero() -> None:
    """Zero price returns zero."""
    assert normalize_price(0.0, 0.25) == 0.0

