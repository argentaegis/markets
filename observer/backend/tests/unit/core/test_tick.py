"""Tests for tick normalization utilities — normalize_price, ticks_between.

Covers ES (tick_size=0.25), CL (tick_size=0.01), and edge cases.
Verifies float-in / float-out API with internal Decimal precision.
"""

from __future__ import annotations

import pytest

from core.tick import normalize_price, ticks_between


class TestNormalizePrice:
    def test_es_rounds_down(self):
        # 5412.30 -> nearest 0.25 tick -> 5412.25
        assert normalize_price(5412.30, 0.25) == 5412.25

    def test_es_rounds_up(self):
        # 5412.40 -> nearest 0.25 tick -> 5412.50
        assert normalize_price(5412.40, 0.25) == 5412.50

    def test_es_exact_tick(self):
        assert normalize_price(5412.25, 0.25) == 5412.25

    def test_es_midpoint_rounds_half(self):
        # 5412.125 is exactly between 5412.00 and 5412.25
        # Decimal ROUND_HALF_EVEN: .125 / .25 = 0.5 -> rounds to nearest even (0)
        # so 0 * 0.25 + 5412.00 = 5412.00... let's check:
        # Actually: 5412.125 / 0.25 = 21648.5 -> ROUND_HALF_EVEN -> 21648
        # 21648 * 0.25 = 5412.00
        result = normalize_price(5412.125, 0.25)
        assert result == 5412.00

    def test_cl_small_tick(self):
        # CL tick_size = 0.01; 72.346 rounds to 72.35
        assert normalize_price(72.346, 0.01) == 72.35

    def test_cl_exact_tick(self):
        assert normalize_price(72.34, 0.01) == 72.34

    def test_returns_float(self):
        result = normalize_price(5412.30, 0.25)
        assert isinstance(result, float)

    def test_zero_price(self):
        assert normalize_price(0.0, 0.25) == 0.0

    def test_negative_price(self):
        # Some instruments can have negative prices (e.g. oil futures in 2020)
        result = normalize_price(-0.30, 0.25)
        assert result == -0.25


class TestTicksBetween:
    def test_es_basic(self):
        # 5412.25 to 5413.25 = 4 ticks at 0.25
        assert ticks_between(5412.25, 5413.25, 0.25) == 4

    def test_es_one_tick(self):
        assert ticks_between(5412.25, 5412.50, 0.25) == 1

    def test_zero_distance(self):
        assert ticks_between(5412.25, 5412.25, 0.25) == 0

    def test_negative_direction(self):
        # price_b < price_a -> negative ticks
        assert ticks_between(5413.25, 5412.25, 0.25) == -4

    def test_cl_small_tick(self):
        # 72.34 to 72.44 = 10 ticks at 0.01
        assert ticks_between(72.34, 72.44, 0.01) == 10

    def test_returns_int(self):
        result = ticks_between(5412.25, 5413.25, 0.25)
        assert isinstance(result, int)

    def test_large_distance(self):
        # 100 points on ES = 400 ticks
        assert ticks_between(5400.00, 5500.00, 0.25) == 400
