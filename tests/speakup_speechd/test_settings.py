# Copyright (C) 2026 Nick Stockton
# SPDX-License-Identifier: GPL-2.0-only
# This program is free software; you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation; version 2 of the License.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# file `LICENSE` for more details.

"""Tests for settings."""

# Future Modules:
from __future__ import annotations

# Built-in Modules:
import logging
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Third-party Modules:
import speechd

# Speakup-speechd Modules:
from speakup_speechd.main import Settings


class TestSettings(unittest.TestCase):
	"""Unit tests for the Settings class."""

	def setUp(self) -> None:
		"""Disable logging at CRITICAL level before each test."""
		self.oldLoggerValue = logging.getLogger().getEffectiveLevel()
		logging.disable(logging.CRITICAL)

	def tearDown(self) -> None:
		"""Restore the original logging level after each test."""
		logging.disable(self.oldLoggerValue)

	def test_init_defaults(self) -> None:
		"""Test __init__ sets correct default values."""
		callback_mock: MagicMock = MagicMock()
		settings: Settings = Settings(callback_mock)
		self.assertIsNone(settings._config_path)  # Default.
		self.assertEqual(settings.data_mode, speechd.DataMode.SSML)
		self.assertEqual(settings.rate, 2)
		self.assertEqual(settings.pitch, 5)
		self.assertEqual(settings.volume, 5)
		self.assertEqual(settings.punctuation, 1)
		self.assertFalse(settings.pause)
		self.assertIsNone(settings.language)
		self.assertIsNone(settings.voice)

	@patch("speakup_speechd.main.logger")
	def test_data_mode_setter(self, mock_logger: MagicMock) -> None:
		"""Test data_mode property setter."""
		callback_mock: MagicMock = MagicMock()
		settings: Settings = Settings(callback_mock)
		settings.data_mode = "TEXT"
		self.assertEqual(settings.data_mode, "TEXT")
		callback_mock.assert_called_once_with("set_data_mode", "TEXT")
		mock_logger.debug.assert_called_once_with("Data mode: TEXT.")

	@patch("speakup_speechd.main.logger")
	def test_pause_setter(self, mock_logger: MagicMock) -> None:
		"""Test pause property setter (calls pause/resume)."""
		callback_mock: MagicMock = MagicMock()
		settings: Settings = Settings(callback_mock)
		settings.pause = True
		self.assertTrue(settings.pause)
		callback_mock.assert_called_once_with("pause")
		mock_logger.debug.assert_called_once_with("pause.")
		callback_mock.reset_mock()
		mock_logger.reset_mock()
		settings.pause = False
		self.assertFalse(settings.pause)
		callback_mock.assert_called_once_with("resume")
		mock_logger.debug.assert_called_once_with("resume.")

	@patch("speakup_speechd.main.logger")
	def test_pitch_setter(self, mock_logger: MagicMock) -> None:
		"""Test pitch setter with Speakup-scale transformation and clamping."""
		callback_mock: MagicMock = MagicMock()
		settings: Settings = Settings(callback_mock)
		# Below midpoint < 5.
		settings.pitch = 0
		self.assertEqual(settings.pitch, 0)
		callback_mock.assert_called_once_with("set_pitch", -100)
		mock_logger.debug.assert_called_once_with("Pitch: -100.")
		callback_mock.reset_mock()
		mock_logger.reset_mock()
		# Above midpoint > 5.
		settings.pitch = 9
		self.assertEqual(settings.pitch, 9)
		callback_mock.assert_called_once_with("set_pitch", 100)
		mock_logger.debug.assert_called_once_with("Pitch: 100.")

	@patch("speakup_speechd.main.logger")
	def test_punctuation_setter(self, mock_logger: MagicMock) -> None:
		"""Test punctuation setter maps clamped index to PunctuationMode."""
		callback_mock: MagicMock = MagicMock()
		settings: Settings = Settings(callback_mock)
		settings.punctuation = 0
		callback_mock.assert_called_once_with("set_punctuation", speechd.PunctuationMode.NONE)
		mock_logger.debug.assert_called_once_with(f"Punctuation: {speechd.PunctuationMode.NONE}.")
		callback_mock.reset_mock()
		mock_logger.reset_mock()
		settings.punctuation = 2
		callback_mock.assert_called_once_with("set_punctuation", speechd.PunctuationMode.MOST)
		mock_logger.debug.assert_called_once_with(f"Punctuation: {speechd.PunctuationMode.MOST}.")
		callback_mock.reset_mock()
		mock_logger.reset_mock()
		# Out-of-range values are clamped.
		settings.punctuation = 99
		callback_mock.assert_called_once_with("set_punctuation", speechd.PunctuationMode.ALL)
		mock_logger.debug.assert_called_once_with(f"Punctuation: {speechd.PunctuationMode.ALL}.")
		callback_mock.reset_mock()
		mock_logger.reset_mock()
		settings.punctuation = -5
		callback_mock.assert_called_once_with("set_punctuation", speechd.PunctuationMode.NONE)

	@patch("speakup_speechd.main.logger")
	def test_rate_setter(self, mock_logger: MagicMock) -> None:
		"""Test rate setter transformation."""
		callback_mock: MagicMock = MagicMock()
		settings: Settings = Settings(callback_mock)
		settings.rate = 0
		self.assertEqual(settings.rate, 0)
		callback_mock.assert_called_once_with("set_rate", -100)
		mock_logger.debug.assert_called_once_with("Rate: -100.")

	@patch("speakup_speechd.main.logger")
	def test_volume_setter(self, mock_logger: MagicMock) -> None:
		"""Test volume setter with Speakup-scale transformation and clamping."""
		callback_mock: MagicMock = MagicMock()
		settings: Settings = Settings(callback_mock)
		settings.volume = 10
		self.assertEqual(settings.volume, 10)
		callback_mock.assert_called_once_with("set_volume", 100)
		mock_logger.debug.assert_called_once_with("Volume: 100.")

	@patch("speakup_speechd.main.logger")
	def test_language_setter(self, mock_logger: MagicMock) -> None:
		"""Test language setter logs always but only calls callback for truthy values."""
		callback_mock: MagicMock = MagicMock()
		settings: Settings = Settings(callback_mock)
		settings.language = None
		self.assertIsNone(settings.language)
		callback_mock.assert_not_called()
		mock_logger.debug.assert_called_once_with("Language: None.")
		callback_mock.reset_mock()
		mock_logger.reset_mock()
		settings.language = "en"
		self.assertEqual(settings.language, "en")
		callback_mock.assert_called_once_with("set_language", "en")
		mock_logger.debug.assert_called_once_with("Language: en.")

	@patch("speakup_speechd.main.logger")
	def test_voice_setter(self, mock_logger: MagicMock) -> None:
		"""Test voice setter logs always but only calls callback for truthy values."""
		callback_mock: MagicMock = MagicMock()
		settings: Settings = Settings(callback_mock)
		settings.voice = None
		self.assertIsNone(settings.voice)
		callback_mock.assert_not_called()
		mock_logger.debug.assert_called_once_with("Voice: None.")
		callback_mock.reset_mock()
		mock_logger.reset_mock()
		settings.voice = "english"
		self.assertEqual(settings.voice, "english")
		callback_mock.assert_called_once_with("set_synthesis_voice", "english")
		mock_logger.debug.assert_called_once_with("Voice: english.")

	@patch("speakup_speechd.main.logger")
	def test_init_speech(self, mock_logger: MagicMock) -> None:
		"""Test init_speech reapplies all stored settings (triggers setters/callbacks)."""
		callback_mock: MagicMock = MagicMock()
		settings: Settings = Settings(callback_mock)
		# Manually set internal state, bypassing setters.
		settings._data_mode = "TEXT"
		settings._rate = 3
		settings._pitch = 6
		settings._volume = 4
		settings._punctuation = 2
		settings._pause = True
		settings._language = "de"
		settings._voice = "german"
		callback_mock.reset_mock()
		mock_logger.reset_mock()
		settings.init_speech()
		# 8 calls expected; language + voice are truthy.
		self.assertEqual(callback_mock.call_count, 8)
		callback_mock.assert_has_calls(
			[
				unittest.mock.call("set_data_mode", "TEXT"),
				unittest.mock.call("set_rate", unittest.mock.ANY),
				unittest.mock.call("set_pitch", unittest.mock.ANY),
				unittest.mock.call("set_volume", unittest.mock.ANY),
				unittest.mock.call("set_punctuation", unittest.mock.ANY),
				unittest.mock.call("pause"),
				unittest.mock.call("set_language", "de"),
				unittest.mock.call("set_synthesis_voice", "german"),
			],
			any_order=False,
		)

	@patch("speakup_speechd.main.logger")
	def test_load_config_no_config_path(self, mock_logger: MagicMock) -> None:
		"""Test load_config when config_path is None."""
		callback_mock: MagicMock = MagicMock()
		settings: Settings = Settings(callback_mock, config_path=None)
		settings.load_config()
		mock_logger.warning.assert_called_once_with(
			"Unable to load configuration file; configuration undefined."
		)

	@patch("speakup_speechd.main.Path.exists")
	@patch("speakup_speechd.main.logger")
	def test_load_config_file_not_exists(self, mock_logger: MagicMock, mock_exists: MagicMock) -> None:
		"""Test load_config when the config file does not exist."""
		mock_exists.return_value = False
		config_path: Path = Path("/nonexistent/config.ini")
		callback_mock: MagicMock = MagicMock()
		settings: Settings = Settings(callback_mock, config_path=config_path)
		settings.load_config()
		mock_exists.assert_called_once()
		mock_logger.warning.assert_called_once_with(f"Configuration file '{config_path}' does not exist.")

	@patch("speakup_speechd.main.configparser.ConfigParser")
	@patch("speakup_speechd.main.Path.exists")
	def test_load_config_success(self, mock_exists: MagicMock, mock_config_parser: MagicMock) -> None:
		"""Test load_config successfully reads language and voice from config."""
		mock_exists.return_value = True
		mock_parser = mock_config_parser.return_value
		mock_parser.__contains__.return_value = True
		section: dict[str, str] = {"language": "fr", "voice": "french"}
		mock_parser.__getitem__.return_value = section
		config_path: Path = Path("/valid/config.ini")
		callback_mock: MagicMock = MagicMock()
		settings: Settings = Settings(callback_mock, config_path=config_path)
		settings.load_config()
		mock_parser.read.assert_called_once_with(config_path)
		self.assertEqual(settings.language, "fr")
		self.assertEqual(settings.voice, "french")
		# Setters were triggered.
		callback_mock.assert_has_calls(
			[
				unittest.mock.call("set_language", "fr"),
				unittest.mock.call("set_synthesis_voice", "french"),
			],
			any_order=True,
		)

	@patch("speakup_speechd.main.configparser.ConfigParser")
	@patch("speakup_speechd.main.Path.exists")
	@patch("speakup_speechd.main.logger")
	def test_load_config_no_section(
		self,
		mock_logger: MagicMock,
		mock_exists: MagicMock,
		mock_config_parser: MagicMock,
	) -> None:
		"""Test load_config when the [speech-dispatcher] section is missing."""
		mock_exists.return_value = True
		mock_parser = mock_config_parser.return_value
		mock_parser.__contains__.return_value = False
		callback_mock: MagicMock = MagicMock()
		settings: Settings = Settings(callback_mock, config_path=Path("config.ini"))
		settings.load_config()
		mock_logger.debug.assert_called_once_with(
			"No [speech-dispatcher] section found in config file: config.ini"
		)
