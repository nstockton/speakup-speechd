# Copyright (C) 2026 Nick Stockton
# SPDX-License-Identifier: GPL-2.0-only
# This program is free software; you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation; version 2 of the License.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# file `LICENSE` for more details.

"""Tests for utility functions."""

# Future Modules:
from __future__ import annotations

# Built-in Modules:
import unittest

# Speakup-speechd Modules:
from speakup_speechd.main import clamp, find_any, iter_bytes


class TestClamp(unittest.TestCase):
	"""Tests for clamp."""

	def test_value_inside_range(self) -> None:
		"""Value already between min and max is returned unchanged."""
		self.assertEqual(clamp(5, 0, 10), 5)
		self.assertEqual(clamp(0, 0, 10), 0)
		self.assertEqual(clamp(10, 0, 10), 10)
		self.assertEqual(clamp(-3, -10, 10), -3)

	def test_value_below_minimum(self) -> None:
		"""Value < minimum returns minimum."""
		self.assertEqual(clamp(-5, 0, 10), 0)
		self.assertEqual(clamp(-15, -10, 5), -10)

	def test_value_above_maximum(self) -> None:
		"""Value > maximum returns maximum."""
		self.assertEqual(clamp(15, 0, 10), 10)
		self.assertEqual(clamp(7, -5, 5), 5)

	def test_boundaries(self) -> None:
		"""Values exactly equal to min or max are not changed."""
		self.assertEqual(clamp(0, 0, 10), 0)
		self.assertEqual(clamp(10, 0, 10), 10)
		self.assertEqual(clamp(-5, -5, 5), -5)
		self.assertEqual(clamp(5, -5, 5), 5)

	def test_min_equals_max(self) -> None:
		"""When minimum == maximum, result is always that value."""
		self.assertEqual(clamp(5, 7, 7), 7)
		self.assertEqual(clamp(7, 7, 7), 7)
		self.assertEqual(clamp(10, 7, 7), 7)
		self.assertEqual(clamp(-5, 7, 7), 7)

	def test_negative_range(self) -> None:
		"""Works correctly when both limits are negative."""
		self.assertEqual(clamp(-18, -20, -15), -18)
		self.assertEqual(clamp(-22, -20, -15), -20)  # Below min.
		self.assertEqual(clamp(-10, -20, -15), -15)  # Above max.


class TestFindAny(unittest.TestCase):
	"""Tests for find_any."""

	def test_empty_values_returns_zero(self) -> None:
		"""Empty `values` iterable always returns 0 (even for empty sequence)."""
		self.assertEqual(find_any([1, 2, 3], []), 0)
		self.assertEqual(find_any([], []), 0)
		self.assertEqual(find_any("abc", ""), 0)  # Empty str is falsy.
		self.assertEqual(find_any(b"abc", b""), 0)  # Empty bytes is falsy.

	def test_empty_sequence_returns_minus_one(self) -> None:
		"""Empty sequence with non-empty values returns -1."""
		self.assertEqual(find_any([], [1, 2, 3]), -1)
		self.assertEqual(find_any("", "xyz"), -1)
		self.assertEqual(find_any(b"", [97]), -1)  # Bytes sequence.

	def test_no_match_returns_minus_one(self) -> None:
		"""No element from `values` present → -1."""
		self.assertEqual(find_any([1, 2, 3], [4, 5, 6]), -1)
		self.assertEqual(find_any("hello", "xyz"), -1)
		self.assertEqual(find_any(b"hello", b"xyz"), -1)  # Integers not present.

	def test_first_occurrence_of_any_value(self) -> None:
		"""Returns index of the *first* matching element from `values`."""
		self.assertEqual(find_any([1, 2, 3, 2], [2, 4]), 1)
		self.assertEqual(find_any("abcde", "ce"), 2)  # 'c' appears before 'e'.
		self.assertEqual(find_any("hello", "lo"), 2)  # 'l' first.

	def test_various_sequence_types(self) -> None:
		"""Works with list, tuple, str, bytes (when element types match)."""
		self.assertEqual(find_any((10, 20, 30), [20]), 1)  # Tuple.
		self.assertEqual(find_any("python", {"y", "t"}), 1)  # String + set.
		# Bytes elements are ints; values must be ints.
		self.assertEqual(find_any(b"data", [97]), 1)  # 'a' is 97 in ASCII.

	def test_various_values_iterables(self) -> None:
		"""`values` can be any iterable (list, tuple, set, etc.)."""
		self.assertEqual(find_any([1, 2, 3], (2, 4)), 1)
		self.assertEqual(find_any(["a", "b", "c"], {"b"}), 1)


class TestIterBytes(unittest.TestCase):
	"""Tests for iter_bytes."""

	def test_empty_bytes_yields_nothing(self) -> None:
		"""Empty input produces an empty iterator."""
		self.assertEqual(list(iter_bytes(b"")), [])

	def test_single_byte(self) -> None:
		"""One-byte input yields a single one-byte `bytes` object."""
		result = list(iter_bytes(b"A"))
		self.assertEqual(result, [b"A"])
		self.assertIsInstance(result[0], bytes)
		self.assertEqual(len(result[0]), 1)

	def test_multiple_bytes(self) -> None:
		"""Each byte is yielded as its own one-byte `bytes` object."""
		data = b"abc"
		result = list(iter_bytes(data))
		self.assertEqual(result, [b"a", b"b", b"c"])

	def test_binary_and_control_bytes(self) -> None:
		"""Handles null, high-bit, and non-ASCII bytes correctly."""
		data = b"\x00\xff\x80\x01"
		result = list(iter_bytes(data))
		expected = [b"\x00", b"\xff", b"\x80", b"\x01"]
		self.assertEqual(result, expected)
		for b in result:
			self.assertIsInstance(b, bytes)
			self.assertEqual(len(b), 1)

	def test_generator_protocol(self) -> None:
		"""Object behaves as a proper generator (supports next/StopIteration)."""
		gen = iter_bytes(b"xy")
		self.assertEqual(next(gen), b"x")
		self.assertEqual(next(gen), b"y")
		with self.assertRaises(StopIteration):
			next(gen)
