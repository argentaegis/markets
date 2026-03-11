"""Tests for tick utilities."""

from __future__ import annotations

import pytest

from strategizer.tick import normalize_price, ticks_between


def test_normalize_price_rounds_to_tick() -> None:
    assert normalize_price(5412.30, 0.25) == 5412.25
    assert normalize_price(5412.38, 0.25) == 5412.50


def test_normalize_price_exact_tick() -> None:
    assert normalize_price(5412.25, 0.25) == 5412.25


def test_normalize_price_small_tick() -> None:
    assert normalize_price(72.456, 0.01) == 72.46


def test_ticks_between_positive() -> None:
    assert ticks_between(5400.0, 5410.0, 0.25) == 40


def test_ticks_between_negative() -> None:
    assert ticks_between(5410.0, 5400.0, 0.25) == -40


def test_ticks_between_zero() -> None:
    assert ticks_between(5400.0, 5400.0, 0.25) == 0


def test_ticks_between_or_range() -> None:
    # OR high 5410, low 5405 = 20 ticks
    assert ticks_between(5405.0, 5410.0, 0.25) == 20
