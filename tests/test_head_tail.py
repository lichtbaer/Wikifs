"""Tests for head/tail line slicing helpers."""

from __future__ import annotations

from wikifs.head_tail import (
    apply_head_tail,
    parse_lines_flag,
    slice_head,
    slice_tail,
)


def test_slice_head_default_lines() -> None:
    text = "a\nb\nc\nd\ne"
    assert slice_head(text, 3) == "a\nb\nc"
    assert slice_head(text, 10) == text


def test_slice_head_zero() -> None:
    assert slice_head("a\nb", 0) == ""


def test_slice_tail() -> None:
    text = "a\nb\nc\nd"
    assert slice_tail(text, 2) == "c\nd"
    assert slice_tail(text, 0) == ""


def test_parse_lines_flag_default() -> None:
    n, err = parse_lines_flag([], default=10)
    assert err is None
    assert n == 10


def test_parse_lines_flag_last_wins() -> None:
    n, err = parse_lines_flag(["-n", "3", "--lines", "7"])
    assert err is None
    assert n == 7


def test_apply_head_tail_cat_unchanged() -> None:
    t = "one\ntwo"
    out, err = apply_head_tail(t, "cat", [])
    assert err is None
    assert out == t


def test_apply_head_tail_head() -> None:
    t = "1\n2\n3\n4"
    out, err = apply_head_tail(t, "head", ["-n", "2"])
    assert err is None
    assert out == "1\n2"
