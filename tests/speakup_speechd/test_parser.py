# Copyright (C) 2026 Nick Stockton
# SPDX-License-Identifier: GPL-2.0-only
# This program is free software; you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation; version 2 of the License.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# file `LICENSE` for more details.

"""Tests for Speakup parser."""

# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
import tempfile
import unittest
import uuid
from codecs import IncrementalDecoder
from pathlib import Path
from unittest.mock import MagicMock, patch

# Speakup-speechd Modules:
from speakup_speechd.main import (
	DTLK_CMD,
	DTLK_CONTROL_ORDINALS,
	DTLK_STOP,
	LATIN1,
	UTF8,
	ParseState,
	Sign,
	SpeakupParser,
	ssml_escape_text,
)


class TestSpeakupParser(unittest.TestCase):
	"""Unit tests for the SpeakupParser class."""

	def setUp(self) -> None:
		"""Disable logging at CRITICAL level before each test."""
		self.oldLoggerValue = logging.getLogger().getEffectiveLevel()
		logging.disable(logging.CRITICAL)

	def tearDown(self) -> None:
		"""Restore the original logging level after each test."""
		logging.disable(self.oldLoggerValue)

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_init_default(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test SpeakupParser default initialization values."""
		parser = SpeakupParser()
		self.assertIsNone(parser.connection)
		mock_softsynth_cls.assert_called_once_with()
		mock_settings_cls.assert_called_once_with(parser.settings_callback, config_path=None)
		self.assertIsInstance(parser._utf8_decoder, IncrementalDecoder)
		self.assertFalse(parser._is_speaking)
		self.assertEqual(parser._state, ParseState.TEXT)
		self.assertEqual(parser._pending_text, bytearray())
		self.assertEqual(parser._ssml_parts, [])
		self.assertEqual(parser._sign, Sign.ZERO)
		self.assertEqual(parser._param, 0)

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_init_with_config_path(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test SpeakupParser initialization passing a custom config_path."""
		config: Path = Path(tempfile.gettempdir()) / uuid.uuid4().hex
		parser = SpeakupParser(config_path=config)
		mock_settings_cls.assert_called_once_with(parser.settings_callback, config_path=config)

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_context_manager(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test SpeakupParser supports the context manager protocol."""
		parser = SpeakupParser()
		with patch.object(parser, "close") as mock_close:
			with parser as p:
				self.assertIs(p, parser)
			mock_close.assert_called_once_with()

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_del_calls_close(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test that __del__ invokes the close method."""
		parser = SpeakupParser()
		with patch.object(parser, "close") as mock_close:
			parser.__del__()
			mock_close.assert_called_once_with()

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.time")
	@patch("speakup_speechd.main.speechd")
	def test_open_softsynth_success_on_first_try(
		self,
		mock_speechd: MagicMock,
		mock_time: MagicMock,
		mock_settings_cls: MagicMock,
		mock_softsynth_cls: MagicMock,
	) -> None:
		"""Test open_softsynth succeeds immediately when fd is already open."""
		mock_soft = mock_softsynth_cls.return_value
		mock_soft.fd = 42  # Already open.
		parser = SpeakupParser()
		parser.open_softsynth()
		mock_soft.open.assert_called_once_with()
		mock_time.sleep.assert_not_called()

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.time")
	@patch("speakup_speechd.main.speechd")
	def test_open_softsynth_retries_until_success(
		self,
		mock_speechd: MagicMock,
		mock_time: MagicMock,
		mock_settings_cls: MagicMock,
		mock_softsynth_cls: MagicMock,
	) -> None:
		"""Test open_softsynth retries on OSError until the device opens."""
		mock_soft = mock_softsynth_cls.return_value
		mock_soft.fd = None
		calls = []

		def open_side_effect() -> None:
			calls.append(1)
			if len(calls) == 1:
				raise OSError("device busy")
			mock_soft.fd = 42

		mock_soft.open.side_effect = open_side_effect
		parser = SpeakupParser()
		parser.open_softsynth()
		self.assertEqual(mock_soft.open.call_count, 2)
		mock_time.sleep.assert_called_once_with(1)

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.time")
	@patch("speakup_speechd.main.speechd")
	def test_connect_speech_dispatcher_success_on_first_try(
		self,
		mock_speechd: MagicMock,
		mock_time: MagicMock,
		mock_settings_cls: MagicMock,
		mock_softsynth_cls: MagicMock,
	) -> None:
		"""Test connect_speech_dispatcher succeeds on the first SSIPClient call."""
		parser = SpeakupParser()
		parser.connect_speech_dispatcher()
		mock_speechd.SSIPClient.assert_called_once_with("speakup", "softsynth", "root")
		self.assertIsNotNone(parser.connection)
		mock_time.sleep.assert_not_called()

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.time")
	@patch("speakup_speechd.main.speechd")
	def test_connect_speech_dispatcher_retries_until_success(
		self,
		mock_speechd: MagicMock,
		mock_time: MagicMock,
		mock_settings_cls: MagicMock,
		mock_softsynth_cls: MagicMock,
	) -> None:
		"""Test connect_speech_dispatcher retries SSIPClient until it succeeds."""
		mock_connection: MagicMock = MagicMock()
		mock_speechd.SSIPClient.side_effect = [Exception("connection failed"), mock_connection]
		parser = SpeakupParser()
		parser.connect_speech_dispatcher()
		self.assertEqual(mock_speechd.SSIPClient.call_count, 2)
		mock_time.sleep.assert_called_once_with(1)
		self.assertIs(parser.connection, mock_connection)

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_connect_full_flow(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test the full connect method orchestrates softsynth, speechd, and settings init."""
		parser = SpeakupParser()
		parser.connection = MagicMock()
		with (
			patch("speakup_speechd.main.logger") as mock_logger,
			patch.object(parser, "open_softsynth") as mock_open_softsynth,
			patch.object(parser, "connect_speech_dispatcher") as mock_connect_sd,
			patch.object(parser.settings, "init_speech") as mock_init_speech,
		):
			parser.connect()
			mock_open_softsynth.assert_called_once_with()
			mock_connect_sd.assert_called_once_with()
			mock_init_speech.assert_called_once_with()
			self.assertEqual(mock_logger.info.call_count, 2)

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_close(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test close resets state, closes the speechd connection, and closes softsynth."""
		parser = SpeakupParser()
		mock_connection: MagicMock = MagicMock()
		parser.connection = mock_connection
		with patch.object(parser, "_reset_state") as mock_reset:
			parser.close()
			mock_reset.assert_called_once_with()
			mock_connection.close.assert_called_once_with()
			self.assertIsNone(parser.connection)
			mock_softsynth_cls.return_value.close.assert_called_once_with()

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_reset_state(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test _reset_state clears buffers, resets decoder, and returns to TEXT state."""
		parser = SpeakupParser()
		parser._pending_text.extend(b"foo")
		parser._ssml_parts.append("bar")
		parser._state = ParseState.PARAM
		parser._sign = Sign.PLUS
		parser._param = 99
		parser._utf8_decoder = MagicMock()
		parser._reset_state()
		parser._utf8_decoder.reset.assert_called_once_with()
		self.assertEqual(parser._pending_text, bytearray())
		self.assertEqual(parser._ssml_parts, [])
		self.assertEqual(parser._sign, Sign.ZERO)
		self.assertEqual(parser._param, 0)
		self.assertEqual(parser._state, ParseState.TEXT)

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_sd_callback_index_mark(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test sd_callback for INDEX_MARK writes the mark to the softsynth."""
		parser = SpeakupParser()
		mock_soft = mock_softsynth_cls.return_value
		parser.sd_callback(mock_speechd.CallbackType.INDEX_MARK, index_mark="42")
		mock_soft.write.assert_called_once_with(b"42")

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_sd_callback_begin_end(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test sd_callback toggles _is_speaking on BEGIN and END events."""
		parser = SpeakupParser()
		parser.sd_callback(mock_speechd.CallbackType.BEGIN)
		self.assertTrue(parser._is_speaking)
		parser.sd_callback(mock_speechd.CallbackType.END)
		self.assertFalse(parser._is_speaking)

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_settings_callback(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test settings_callback forwards method calls to the speechd connection."""
		parser = SpeakupParser()
		parser.connection = MagicMock()
		parser.settings_callback("set_rate", 123, foo="bar")
		parser.connection.set_rate.assert_called_once_with(123, foo="bar")

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_settings_callback_no_connection(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test settings_callback does not raise when connection is None."""
		parser = SpeakupParser()
		parser.connection = None
		# Should not raise.
		parser.settings_callback("set_rate", 123)

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_list_modules(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test list_modules delegates to connection.list_output_modules."""
		parser = SpeakupParser()
		parser.connection = MagicMock()
		parser.connection.list_output_modules.return_value = ("espeak-ng", "viavoice")
		result = parser.list_modules()
		parser.connection.list_output_modules.assert_called_once_with()
		self.assertEqual(result, ("espeak-ng", "viavoice"))

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_list_modules_no_connection(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test list_modules returns empty tuple when no connection exists."""
		parser = SpeakupParser()
		self.assertEqual(parser.list_modules(), ())

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_list_voices(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test list_voices delegates to connection.list_synthesis_voices."""
		parser = SpeakupParser()
		parser.connection = MagicMock()
		parser.connection.list_synthesis_voices.return_value = (("voice1", "en", "variant1"),)
		result = parser.list_voices(language="en", variant="variant1")
		parser.connection.list_synthesis_voices.assert_called_once_with("en", "variant1")
		self.assertEqual(result, (("voice1", "en", "variant1"),))

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_list_voices_no_connection(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test list_voices returns empty tuple when no connection exists."""
		parser = SpeakupParser()
		self.assertEqual(parser.list_voices(), ())

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_is_speaking_property(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test the is_speaking read-only property reflects internal flag."""
		parser = SpeakupParser()
		self.assertFalse(parser.is_speaking)
		parser._is_speaking = True
		self.assertTrue(parser.is_speaking)

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	@patch("speakup_speechd.main.find_any", return_value=-1)
	def test_feed_fast_path_text_only(
		self,
		mock_find_any: MagicMock,
		mock_speechd: MagicMock,
		mock_settings_cls: MagicMock,
		mock_softsynth_cls: MagicMock,
	) -> None:
		"""Test feed fast-path for plain text with no control characters."""
		parser = SpeakupParser()
		mock_soft = mock_softsynth_cls.return_value
		mock_soft.encoding = "utf-8"
		with (
			patch.object(parser, "_flush_pending_text") as mock_flush_text,
			patch.object(parser, "_flush_ssml") as mock_flush_ssml,
		):
			data = b"plain text no control"
			parser.feed(data)
			self.assertEqual(parser._pending_text, bytearray(b"plain text no control"))
			mock_flush_text.assert_called_once_with()
			mock_flush_ssml.assert_called_once_with()
			mock_find_any.assert_called_once_with(data, DTLK_CONTROL_ORDINALS)

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_feed_text_in_non_fast_path(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test text accumulation in _handle_text_state when fast path is not taken."""
		parser = SpeakupParser()
		parser.connection = MagicMock()
		mock_soft = mock_softsynth_cls.return_value
		mock_soft.encoding = UTF8
		# Presence of control char forces byte-by-byte processing.
		segments: tuple[bytes, ...] = (b"hello", DTLK_CMD + b"1p", b"world")
		parser.feed(b"".join(segments))
		# Both text segments are flushed to SSML in the slow path. We verify via the speak calls
		# because _flush_ssml clears _ssml_parts after each call to speak.
		text_segments: tuple[str, ...] = (str(segments[0], "ascii"), str(segments[-1], "ascii"))
		self.assertEqual(parser.connection.speak.call_count, len(text_segments))
		ssml_calls = [call[0][0] for call in parser.connection.speak.call_args_list]
		for text_segment, ssml_call in zip(text_segments, ssml_calls, strict=True):
			self.assertEqual(f"<speak>{text_segment}</speak>", ssml_call)

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_feed_stop_command_resets(
		self,
		mock_speechd: MagicMock,
		mock_settings_cls: MagicMock,
		mock_softsynth_cls: MagicMock,
	) -> None:
		"""Test feed of DTLK_STOP cancels speech and resets parser state."""
		parser = SpeakupParser()
		parser.connection = MagicMock()
		with patch.object(parser, "_reset_state") as mock_reset:
			parser.feed(DTLK_STOP)
			parser.connection.cancel.assert_called_once_with()
			mock_reset.assert_called_once_with()

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_feed_commands_with_absolute_parameters(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test _handle_cmd_start_state for absolute commands."""
		parser = SpeakupParser()
		parser.connection = MagicMock()
		# Punctuation.
		parser.feed(DTLK_CMD + b"3b")
		self.assertEqual(parser.settings.punctuation, 3)
		# Pause.
		parser.settings.pause = True
		parser.feed(DTLK_CMD + b"P")
		self.assertFalse(parser.settings.pause)

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_feed_command_with_relative_parameters(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test _handle_cmd_start_state for + and - signs."""
		parser = SpeakupParser()
		parser.connection = MagicMock()
		parser.settings.pitch = 5
		parser.settings.rate = 5
		parser.settings.volume = 5
		# Relative increment pitch.
		parser.feed(DTLK_CMD + b"+3p")
		self.assertEqual(parser.settings.pitch, 8)
		# Relative decrement rate.
		parser.feed(DTLK_CMD + b"-2s")
		self.assertEqual(parser.settings.rate, 3)
		# Relative volume without digit does not change value.
		parser.feed(DTLK_CMD + b"+v")
		self.assertEqual(parser.settings.volume, 5)

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_feed_bare_commands(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test bare commands (no sign, no digits) in _handle_cmd_start_state."""
		parser = SpeakupParser()
		parser.connection = MagicMock()
		parser.settings.punctuation = 1
		parser.feed(DTLK_CMD + b"b")  # Bare punctuation command.
		self.assertEqual(parser.settings.punctuation, 0)  # Param defaults to 0.
		parser.settings.pause = False
		parser.feed(DTLK_CMD + b"P")  # Bare pause command.
		self.assertTrue(parser.settings.pause)

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_feed_index_mark_inside_utterance(
		self,
		mock_speechd: MagicMock,
		mock_settings_cls: MagicMock,
		mock_softsynth_cls: MagicMock,
	) -> None:
		"""Test feed of index-mark command inserts SSML mark and flushes."""
		parser = SpeakupParser()
		parser.connection = None  # no flush
		with (
			patch.object(parser, "_flush_pending_text") as mock_flush_text,
			patch.object(parser, "_flush_ssml") as mock_flush_ssml,
		):
			parser.feed(DTLK_CMD + b"42i")
			# _flush_pending_text is called once inside _handle_command for the 'i' command
			# and once more at the end of feed after the byte loop state is back to TEXT.
			self.assertEqual(mock_flush_text.call_count, 2)
			# _flush_ssml is not called inside _handle_command for the 'i' command
			# but is called at the end of feed after the byte loop state is back to TEXT.
			mock_flush_ssml.assert_called_once_with()
			self.assertIn('<mark name="42"/>', parser._ssml_parts)

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_feed_single_printable_char_uses_char_command(
		self,
		mock_speechd: MagicMock,
		mock_settings_cls: MagicMock,
		mock_softsynth_cls: MagicMock,
	) -> None:
		"""Test feed of a single printable char calls connection.char()."""
		mock_soft = mock_softsynth_cls.return_value
		mock_soft.encoding = UTF8
		parser = SpeakupParser()
		parser.connection = MagicMock()
		parser.feed(b"X")
		parser.connection.char.assert_called_once_with("X")

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_feed_single_char_fallback_to_ssml_on_failure(
		self,
		mock_speechd: MagicMock,
		mock_settings_cls: MagicMock,
		mock_softsynth_cls: MagicMock,
	) -> None:
		"""Test single-char feed falls back to SSML <say-as> on char() exception."""
		mock_soft = mock_softsynth_cls.return_value
		mock_soft.encoding = UTF8
		parser = SpeakupParser()
		parser.connection = MagicMock()
		parser.connection.char.side_effect = Exception("char failed")
		with patch.object(parser, "_flush_ssml") as mock_flush_ssml:
			parser.feed(b"!")
			parser.connection.char.assert_called_once_with("!")
			self.assertIn('<say-as interpret-as="characters">!</say-as>', parser._ssml_parts)
			mock_flush_ssml.assert_called_once_with()

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_feed_multi_char_text_escapes_to_ssml(
		self,
		mock_speechd: MagicMock,
		mock_settings_cls: MagicMock,
		mock_softsynth_cls: MagicMock,
	) -> None:
		"""Test multi-character text is SSML-escaped and added to SSML parts."""
		mock_soft = mock_softsynth_cls.return_value
		mock_soft.encoding = UTF8
		parser = SpeakupParser()
		with patch.object(parser, "_flush_ssml") as mock_flush_ssml:
			parser.feed(b"'Hi!'")
			# SSML escaped but simple text.
			self.assertIn(ssml_escape_text("'Hi!'"), parser._ssml_parts[0])
			mock_flush_ssml.assert_called_once_with()

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_handle_command_reset(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test _handle_command for '@' reset: flushes, closes, and reconnects."""
		parser = SpeakupParser()
		with (
			patch.object(parser, "close") as mock_close,
			patch.object(parser, "connect") as mock_connect,
			patch.object(parser, "_flush_pending_text") as mock_flush_text,
			patch.object(parser, "_flush_ssml") as mock_flush_ssml,
		):
			parser._handle_command(b"@", 0, Sign.ZERO)
			mock_flush_text.assert_called_once_with()
			mock_flush_ssml.assert_called_once_with()
			mock_close.assert_called_once_with()
			mock_connect.assert_called_once_with()

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_handle_command_settings_calls(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test _handle_command updates Settings for pitch/rate (absolute/relative)."""
		parser = SpeakupParser()
		with (
			patch.object(parser, "_flush_pending_text") as mock_flush_text,
			patch.object(parser, "_flush_ssml") as mock_flush_ssml,
		):
			parser.settings.pitch = 4
			parser._handle_command(b"p", 2, Sign.ZERO)  # Exact pitch.
			self.assertEqual(parser.settings.pitch, 2)
			mock_flush_text.assert_called_once_with()
			mock_flush_ssml.assert_called_once_with()
			parser.settings.rate = 4
			parser._handle_command(b"s", 2, Sign.PLUS)  # Relative rate.
			self.assertEqual(parser.settings.rate, 6)

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_handle_command_unknown(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test _handle_command logs unknown commands without raising."""
		parser = SpeakupParser()
		with (
			patch("speakup_speechd.main.logger") as mock_logger,
			patch.object(parser, "_flush_pending_text"),
			patch.object(parser, "_flush_ssml"),
		):
			parser._handle_command(b"z", 10, Sign.MINUS)
			# No exception, just logs unknown command.
			mock_logger.debug.assert_called_once()

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_run_successful_loop_one_iteration(
		self,
		mock_speechd: MagicMock,
		mock_settings_cls: MagicMock,
		mock_softsynth_cls: MagicMock,
	) -> None:
		"""Test run performs one connect/read/feed cycle before KeyboardInterrupt."""
		parser = SpeakupParser()
		mock_soft = mock_softsynth_cls.return_value
		mock_soft.poll_for_read.return_value = True
		with patch.object(parser, "connect") as mock_connect, patch.object(parser, "feed") as mock_feed:
			# Simulate KeyboardInterrupt after one iteration.
			mock_soft.read.side_effect = [b"hello", KeyboardInterrupt]
			parser.run()
			mock_connect.assert_called_once_with()
			mock_feed.assert_called_once_with(b"hello")

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_run_empty_data_read(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test EOF reached in run."""
		parser = SpeakupParser()
		mock_soft = mock_softsynth_cls.return_value
		mock_soft.poll_for_read.return_value = True
		mock_soft.read.return_value = b""  # simulate device closed / EOF
		with patch.object(parser, "connect"), patch("speakup_speechd.main.logger") as mock_logger:
			parser.run()
			mock_logger.info.assert_called_with("Speech bridge terminated.")

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_run_handles_interrupted_error(
		self,
		mock_speechd: MagicMock,
		mock_settings_cls: MagicMock,
		mock_softsynth_cls: MagicMock,
	) -> None:
		"""Test run catches InterruptedError and continues the loop."""
		parser = SpeakupParser()
		mock_soft = mock_softsynth_cls.return_value
		mock_soft.poll_for_read.return_value = True
		with patch.object(parser, "connect") as mock_connect, patch.object(parser, "feed") as mock_feed:
			mock_soft.read.side_effect = [b"hello", InterruptedError, KeyboardInterrupt]
			parser.run()
			mock_connect.assert_called_once_with()
			mock_feed.assert_called_once_with(b"hello")

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_run_handles_oserror(
		self,
		mock_speechd: MagicMock,
		mock_settings_cls: MagicMock,
		mock_softsynth_cls: MagicMock,
	) -> None:
		"""Test run logs OSError from poll_for_read and exits cleanly."""
		parser = SpeakupParser()
		mock_soft = mock_softsynth_cls.return_value
		mock_soft.poll_for_read.side_effect = OSError("read error")
		with patch.object(parser, "connect"), patch("speakup_speechd.main.logger") as mock_logger:
			parser.run()
			mock_logger.exception.assert_called_once_with("Select/read error.")

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_run_handles_exception(
		self,
		mock_speechd: MagicMock,
		mock_settings_cls: MagicMock,
		mock_softsynth_cls: MagicMock,
	) -> None:
		"""Test run logs Exception from poll_for_read and exits cleanly."""
		parser = SpeakupParser()
		mock_soft = mock_softsynth_cls.return_value
		mock_soft.poll_for_read.side_effect = Exception
		with patch.object(parser, "connect"), patch("speakup_speechd.main.logger") as mock_logger:
			parser.run()
			mock_logger.exception.assert_called_once_with("Unexpected error in run loop.")

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_flush_pending_text_latin1(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test _flush_pending_text decodes Latin-1 bytes into SSML parts."""
		parser = SpeakupParser()
		mock_soft = mock_softsynth_cls.return_value
		mock_soft.encoding = LATIN1
		parser._pending_text.extend(b"\xe9")  # E-acute  in Latin-1.
		with patch.object(parser, "_flush_ssml") as mock_flush_ssml:
			parser._flush_pending_text()
			self.assertIn("\xe9", parser._ssml_parts[0])
			mock_flush_ssml.assert_not_called()  # Only called from feed.

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_flush_pending_text_utf8(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test _flush_pending_text decodes UTF-8 bytes into SSML parts."""
		parser = SpeakupParser()
		mock_soft = mock_softsynth_cls.return_value
		mock_soft.encoding = UTF8
		parser._pending_text.extend(b"\xc3\xa9")  # E-acute  in UTF-8.
		with patch.object(parser, "_flush_ssml") as mock_flush_ssml:
			parser._flush_pending_text()
			self.assertIn("\xe9", parser._ssml_parts[0])
			mock_flush_ssml.assert_not_called()  # Only called from feed.

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_flush_pending_text_empty(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test _flush_pending_text is a no-op when pending_text is empty."""
		parser = SpeakupParser()
		parser.connection = MagicMock()
		with patch.object(parser, "_flush_ssml") as mock_flush_ssml:
			parser._flush_pending_text()
			self.assertEqual(parser._pending_text, bytearray())
			self.assertEqual(parser._ssml_parts, [])
			parser.connection.char.assert_not_called()
			mock_flush_ssml.assert_not_called()  # Only called from feed.

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_flush_ssml_sends_speak(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test _flush_ssml concatenates parts into <speak> and calls connection.speak."""
		parser = SpeakupParser()
		parser.connection = MagicMock()
		parser._ssml_parts = ["hello", " world"]
		with patch("speakup_speechd.main.logger") as mock_logger:
			parser._flush_ssml()
			parser.connection.speak.assert_called_once()
			self.assertIn("<speak>hello world</speak>", parser.connection.speak.call_args[0][0])
			mock_logger.debug.assert_called_once()
			self.assertEqual(parser._ssml_parts, [])

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_flush_ssml_when_error_on_speak(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test _flush_ssml is a no-op when connection.speak raises an exception."""
		parser = SpeakupParser()
		parser.connection = MagicMock()
		parser.connection.speak.side_effect = Exception
		parser._ssml_parts = ["hello", " world"]
		with patch("speakup_speechd.main.logger") as mock_logger:
			parser._flush_ssml()
			parser.connection.speak.assert_called_once()
			self.assertIn("<speak>hello world</speak>", parser.connection.speak.call_args[0][0])
			mock_logger.exception.assert_called_once_with("Speak SSML failed.")
			self.assertEqual(parser._ssml_parts, [])

	@patch("speakup_speechd.main.Softsynth")
	@patch("speakup_speechd.main.Settings")
	@patch("speakup_speechd.main.speechd")
	def test_flush_ssml_no_connection_or_no_parts(
		self, mock_speechd: MagicMock, mock_settings_cls: MagicMock, mock_softsynth_cls: MagicMock
	) -> None:
		"""Test _flush_ssml is a no-op with no connection or no SSML parts."""
		parser = SpeakupParser()
		parser._ssml_parts = []
		parser._flush_ssml()  # No-op.
		parser.connection = None
		parser._ssml_parts = ["foo"]
		parser._flush_ssml()  # No-op.

	def test_parse_state_enum(self) -> None:
		"""Test ParseState enum has expected members and positive values."""
		self.assertEqual(len(ParseState), 4)
		self.assertTrue(ParseState.TEXT.value > 0)

	def test_sign_intenum(self) -> None:
		"""Test Sign IntEnum has the three expected sign values."""
		self.assertEqual(Sign.MINUS, -1)
		self.assertEqual(Sign.ZERO, 0)
		self.assertEqual(Sign.PLUS, 1)
