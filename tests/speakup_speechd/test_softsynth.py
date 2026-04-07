# Copyright (C) 2026 Nick Stockton
# SPDX-License-Identifier: GPL-2.0-only
# This program is free software; you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation; version 2 of the License.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# file `LICENSE` for more details.

"""Tests for softsynth wrapper."""

# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
import unittest
from unittest.mock import MagicMock, Mock, call, patch

# Speakup-speechd Modules:
from speakup_speechd.main import (
	BLOCK_SIZE,
	EPOLLIN,
	LATIN1,
	LATIN1_SOFTSYNTH_PATH,
	O_NONBLOCK,
	O_RDWR,
	UTF8,
	UTF8_SOFTSYNTH_PATH,
	Softsynth,
)


class TestSoftsynth(unittest.TestCase):
	"""Tests for Softsynth class."""

	def setUp(self) -> None:
		"""Disable logging at CRITICAL level before each test."""
		self.oldLoggerValue = logging.getLogger().getEffectiveLevel()
		logging.disable(logging.CRITICAL)

	def tearDown(self) -> None:
		"""Restore the original logging level after each test."""
		logging.disable(self.oldLoggerValue)

	@patch("speakup_speechd.main.select")
	@patch("speakup_speechd.main.os")
	def test_init(self, mock_os: Mock, mock_select: Mock) -> None:
		"""Test __init__ sets default state."""
		synth = Softsynth()
		self.assertIsNone(synth.fd)
		self.assertEqual(synth.encoding, UTF8)
		self.assertFalse(synth.is_read_only)
		self.assertIsNone(synth._epoll)

	@patch.object(Softsynth, "close")
	def test_del_calls_close(self, mock_close: Mock) -> None:
		"""Test __del__ delegates to close."""
		synth = Softsynth()
		synth.__del__()
		mock_close.assert_called_once()

	@patch("speakup_speechd.main.select")
	@patch("speakup_speechd.main.os")
	def test_close_nothing_open(self, mock_os: Mock, mock_select: Mock) -> None:
		"""Test close when nothing is open does nothing."""
		synth = Softsynth()
		synth.close()
		self.assertIsNone(synth._epoll)
		self.assertIsNone(synth.fd)
		mock_os.close.assert_not_called()
		mock_select.epoll.assert_not_called()

	@patch("speakup_speechd.main.select")
	@patch("speakup_speechd.main.os")
	def test_close_with_open(self, mock_os: Mock, mock_select: Mock) -> None:
		"""Test close cleans up fd and epoll (including unregister)."""
		synth = Softsynth()
		synth.fd = 42
		mock_epoll = MagicMock()
		synth._epoll = mock_epoll
		synth.close()
		mock_epoll.unregister.assert_called_with(42)
		mock_epoll.close.assert_called_once()
		mock_os.close.assert_called_with(42)
		self.assertIsNone(synth.fd)
		self.assertIsNone(synth._epoll)

	@patch("speakup_speechd.main.select")
	@patch.object(Softsynth, "_get_fd")
	def test_open_already_open(self, mock_get_fd: Mock, mock_select: Mock) -> None:
		"""Test open returns early if already open."""
		synth = Softsynth()
		synth.fd = 10
		synth.open()
		mock_get_fd.assert_not_called()
		mock_select.epoll.assert_not_called()
		synth.fd = None

	@patch("speakup_speechd.main.logger")
	@patch("speakup_speechd.main.select")
	@patch.object(Softsynth, "_get_fd")
	def test_open_utf8_success(self, mock_get_fd: Mock, mock_select: Mock, mock_logger: Mock) -> None:
		"""Test open prefers UTF-8 path and registers epoll."""
		mock_get_fd.return_value = (5, False)
		mock_epoll = MagicMock()
		mock_select.epoll.return_value = mock_epoll
		synth = Softsynth()
		synth.open()
		mock_get_fd.assert_called_once_with(UTF8_SOFTSYNTH_PATH)
		self.assertEqual(synth.fd, 5)
		self.assertFalse(synth.is_read_only)
		self.assertEqual(synth.encoding, UTF8)
		mock_logger.debug.assert_called_with(f"Reading from '{UTF8_SOFTSYNTH_PATH}'.")
		mock_select.epoll.assert_called_once()
		mock_epoll.register.assert_called_once_with(5, EPOLLIN)
		synth.fd = None

	@patch("speakup_speechd.main.logger")
	@patch("speakup_speechd.main.select")
	@patch.object(Softsynth, "_get_fd")
	def test_open_fallback_latin1(self, mock_get_fd: Mock, mock_select: Mock, mock_logger: Mock) -> None:
		"""Test open falls back to Latin-1 on UTF-8 failure."""
		mock_get_fd.side_effect = [OSError, (5, True)]
		mock_epoll = MagicMock()
		mock_select.epoll.return_value = mock_epoll
		synth = Softsynth()
		synth.open()
		self.assertEqual(mock_get_fd.call_args_list, [call(UTF8_SOFTSYNTH_PATH), call(LATIN1_SOFTSYNTH_PATH)])
		self.assertEqual(synth.fd, 5)
		self.assertTrue(synth.is_read_only)
		self.assertEqual(synth.encoding, LATIN1)
		mock_logger.debug.assert_any_call(f"Reading from '{LATIN1_SOFTSYNTH_PATH}'.")
		synth.fd = None

	@patch("speakup_speechd.main.os")
	def test_get_fd_rw_success(self, mock_os: Mock) -> None:
		"""Test _get_fd succeeds with read-write mode."""
		mock_os.open.return_value = 10
		fd, is_read_only = Softsynth._get_fd(UTF8_SOFTSYNTH_PATH)
		self.assertEqual(fd, 10)
		self.assertFalse(is_read_only)
		mock_os.open.assert_called_once_with(UTF8_SOFTSYNTH_PATH, O_RDWR | O_NONBLOCK)

	@patch("speakup_speechd.main.logger")
	@patch("speakup_speechd.main.os")
	def test_get_fd_rw_fail_ro_success(self, mock_os: Mock, mock_logger: Mock) -> None:
		"""Test _get_fd falls back to read-only on RDWR failure."""
		mock_os.open.side_effect = [OSError, 10]
		fd, is_read_only = Softsynth._get_fd(UTF8_SOFTSYNTH_PATH)
		self.assertEqual(fd, 10)
		self.assertTrue(is_read_only)
		self.assertEqual(mock_os.open.call_count, 2)
		mock_logger.debug.assert_called_with(
			f"Unable to open '{UTF8_SOFTSYNTH_PATH}' in read-write mode, trying read-only mode."
		)

	@patch("speakup_speechd.main.logger")
	@patch("speakup_speechd.main.os")
	def test_get_fd_both_fail(self, mock_os: Mock, mock_logger: Mock) -> None:
		"""Test _get_fd raises if both modes fail."""
		mock_os.open.side_effect = OSError
		with self.assertRaises(OSError):
			Softsynth._get_fd(UTF8_SOFTSYNTH_PATH)
		mock_logger.debug.assert_any_call(f"Unable to open '{UTF8_SOFTSYNTH_PATH}' in read-only mode.")

	@patch("speakup_speechd.main.select")
	def test_poll_for_read_no_device(self, mock_select: Mock) -> None:
		"""Test poll_for_read returns False when no device/epoll."""
		synth = Softsynth()
		self.assertFalse(synth.poll_for_read())
		self.assertFalse(synth.poll_for_read(timeout=1.0))

	@patch("speakup_speechd.main.select")
	def test_poll_for_read(self, mock_select: Mock) -> None:
		"""Test poll_for_read returns True/False based on epoll events."""
		synth = Softsynth()
		synth.fd = 5
		mock_epoll = MagicMock()
		mock_epoll.poll.return_value = [(5, EPOLLIN)]
		synth._epoll = mock_epoll
		self.assertTrue(synth.poll_for_read(timeout=0.5))
		mock_epoll.poll.assert_called_with(0.5)
		mock_epoll.poll.return_value = []
		self.assertFalse(synth.poll_for_read())
		synth.fd = None

	@patch("speakup_speechd.main.os")
	def test_read_no_fd(self, mock_os: Mock) -> None:
		"""Test read returns empty bytes when no fd."""
		synth = Softsynth()
		self.assertEqual(synth.read(BLOCK_SIZE), b"")
		mock_os.read.assert_not_called()

	@patch("speakup_speechd.main.os")
	def test_read(self, mock_os: Mock) -> None:
		"""Test read delegates to os.read."""
		synth = Softsynth()
		synth.fd = 10
		mock_os.read.return_value = b"test data"
		data = synth.read(BLOCK_SIZE)
		self.assertEqual(data, b"test data")
		mock_os.read.assert_called_with(10, BLOCK_SIZE)

	@patch("speakup_speechd.main.os")
	def test_write_no_fd(self, mock_os: Mock) -> None:
		"""Test write does nothing when no fd."""
		synth = Softsynth()
		synth.write(b"test data")
		mock_os.write.assert_not_called()

	@patch("speakup_speechd.main.logger")
	@patch("speakup_speechd.main.os")
	def test_write_non_numeric(self, mock_os: Mock, mock_logger: Mock) -> None:
		"""Test write logs warning for non-digit data (no write)."""
		synth = Softsynth()
		synth.fd = 10
		synth.write(b"hello")
		mock_logger.warning.assert_called_once()
		mock_os.write.assert_not_called()

	@patch("speakup_speechd.main.os")
	def test_write_success(self, mock_os: Mock) -> None:
		"""Test write calls os.write for valid numeric index mark."""
		synth = Softsynth()
		synth.fd = 10
		synth.write(b"42")
		mock_os.write.assert_called_with(10, b"42")

	@patch("speakup_speechd.main.os")
	def test_write_suppress_oserror(self, mock_os: Mock) -> None:
		"""Test OSError on write is suppressed (as per contextlib.suppress)."""
		synth = Softsynth()
		synth.fd = 10
		mock_os.write.side_effect = OSError
		synth.write(b"99")  # Must not raise.
		mock_os.write.assert_called_once_with(10, b"99")
