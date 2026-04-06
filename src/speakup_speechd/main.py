#!/usr/bin/env python3

# Copyright (C) 2026 Nick Stockton
# SPDX-License-Identifier: GPL-2.0-only
# This program is free software; you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation; version 2 of the License.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# file `LICENSE` for more details.

"""Python interface between Speakup and Speech Dispatcher."""

# Future Modules:
from __future__ import annotations

# Built-in Modules:
import argparse
import configparser
import logging
import os
import select
import signal
import sys
import time
from codecs import IncrementalDecoder, getincrementaldecoder
from collections.abc import Generator, Iterable, Sequence
from contextlib import suppress
from enum import Enum, IntEnum, auto
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any, Final


if TYPE_CHECKING:  # pragma: no cover
	from .typedef import ListVoicesType, Self, SettingsCallbackType, SSIPClientType, T


try:
	import speechd
except ImportError:  # pragma: no cover
	print("ERROR: speechd Python module not found.", file=sys.stderr)
	print("Install python3-speechd or equivalent package.", file=sys.stderr)
	raise SystemExit(1) from None


# Constants:
BLOCK_SIZE: Final[int] = 1024 * 16  # 16KB.
UTF8: Final[str] = "utf-8"
LATIN1: Final[str] = "latin-1"
# The original /dev/softsynth only supports 8-bit Latin-1.
LATIN1_SOFTSYNTH_PATH: Final[Path] = Path("/dev/softsynth")
# Inside the Linux kernel's virtual console / VT subsystem, characters are stored and
# processed as 16-bit Unicode code points (u16). This covers the entire Basic Multilingual Plane
# but not characters that fall outside the BMP, in the so-called Astral Plane such as most emojis.
# /dev/softsynthu was added in March 2017 to kernel version 4.12 so that the kernel could
# hand Speakup a full 16-bit Unicode value and the driver would convert it on-the-fly into
# proper UTF-8 (1-3 bytes per BMP character).
UTF8_SOFTSYNTH_PATH: Final[Path] = Path("/dev/softsynthu")
DTLK_CMD: Final[bytes] = bytes([1])  # Control-A in Speakup protocol.
DTLK_STOP: Final[bytes] = bytes([24])  # Control-X in Speakup protocol.
DTLK_CONTROL_ORDINALS: Final[frozenset[int]] = frozenset(  # Used for fast text state check.
	DTLK_CMD + DTLK_STOP
)
KNOWN_SOFTSYNTH_COMMANDS: Final[dict[bytes, str]] = {  # Used for logging.
	b"@": "reset",
	b"b": "punctuation",
	b"f": "frequency",
	b"i": "index",
	b"P": "pause",
	b"p": "pitch",
	b"o": "voice",
	b"r": "inflection",
	b"s": "rate",
	b"v": "volume",
	b"x": "tone",
}
PUNCTUATION_MODES: Final[tuple[str, ...]] = (
	speechd.PunctuationMode.NONE,
	speechd.PunctuationMode.SOME,
	speechd.PunctuationMode.MOST,
	speechd.PunctuationMode.ALL,
)
EPOLLIN: Final[int] = getattr(select, "EPOLLIN", 1)
O_RDONLY: Final[int] = getattr(os, "O_RDONLY", 0)
O_RDWR: Final[int] = getattr(os, "O_RDWR", 2)
O_NONBLOCK: Final[int] = getattr(os, "O_NONBLOCK", 2048)
ESCAPE_SSML_STR_ENTITIES: Final[tuple[tuple[str, str], ...]] = (
	("&", "&amp;"),  # & must always be first when escaping.
	("<", "&lt;"),
	(">", "&gt;"),
	("'", "&apos;"),
	('"', "&quot;"),
)


# Globals:
logger: Final[logging.Logger] = logging.getLogger(__name__)


def ssml_escape_text(text: str) -> str:
	"""
	Escapes characters special to SSML.

	Args:
		text: The text to be escaped.

	Returns:
		The escaped text.
	"""
	for old, new in ESCAPE_SSML_STR_ENTITIES:
		text = text.replace(old, new)
	return text


def find_any(sequence: Sequence[T], values: Iterable[T]) -> int:
	"""
	Return the index of the first occurrence in sequence of any value from values.

	This is analogous to str.find but for any sequence and any matching element.

	Args:
		sequence: Sequence to search through.
		values: Values to search for.

	Returns:
		Index of first match, 0 if values empty, or -1 if no match.
	"""
	if not values:
		return 0  # Matches behavior of string.find if empty value supplied.
	for i in range(len(sequence)):  # Faster than enumerate for this use case.
		if sequence[i] in values:
			return i
	return -1


def iter_bytes(data: bytes) -> Generator[bytes, None, None]:
	"""
	Yield each byte of data as a single-byte bytes object.

	Args:
		data: The data to process.

	Yields:
		Each byte of data as bytes.
	"""
	for i in range(len(data)):
		yield data[i : i + 1]


def clamp(value: int, minimum: int, maximum: int) -> int:
	"""
	Clamp a value to be between minimum and maximum.

	Args:
		value: Value to clamp.
		minimum: Lower limit.
		maximum: Upper limit.

	Returns:
		Clamped value.
	"""
	return max(minimum, min(value, maximum))


class Softsynth:
	"""Wrapper around the Speakup softsynth device for reading commands/text and writing index marks."""

	def __init__(self) -> None:
		"""Initialize Softsynth with no open device."""
		self.fd: int | None = None  # The file descriptor of the softsynth device.
		self.encoding: str = UTF8  # The character encoding expected by the softsynth device.
		self._epoll: select.epoll | None = None

	def __del__(self) -> None:
		"""Ensure device is closed on deletion."""
		self.close()

	def close(self) -> None:
		"""Close the file descriptor and epoll instance if open."""
		if self._epoll is not None:
			if self.fd is not None:
				with suppress(OSError):
					self._epoll.unregister(self.fd)
			self._epoll.close()
			self._epoll = None
		if self.fd is not None:
			os.close(self.fd)
			self.fd = None

	def open(self) -> None:
		"""Open the softsynth device preferring UTF-8 support then falling back to Latin-1."""
		if self.fd is not None:
			return  # Device already open.
		try:
			self.fd = self._get_fd(UTF8_SOFTSYNTH_PATH)
			self.encoding = UTF8
			logger.debug(f"Reading from '{UTF8_SOFTSYNTH_PATH}'.")
		except OSError:
			self.fd = self._get_fd(LATIN1_SOFTSYNTH_PATH)
			self.encoding = LATIN1
			logger.debug(f"Reading from '{LATIN1_SOFTSYNTH_PATH}'.")
		if self._epoll is None:
			self._epoll = select.epoll()
			self._epoll.register(self.fd, EPOLLIN)

	@staticmethod
	def _get_fd(softsynth_path: Path) -> int:
		"""
		Open softsynth device, trying read-write mode then read-only.

		Args:
			softsynth_path: Path to device file.

		Returns:
			File descriptor.

		Raises:
			OSError: If device cannot be opened.
		"""
		try:
			return os.open(softsynth_path, O_RDWR | O_NONBLOCK)
		except OSError:
			logger.debug(f"Unable to open '{softsynth_path}' in read-write mode, trying read-only mode.")
			try:
				# Speakup will not receive index marks if this succeeds.
				return os.open(softsynth_path, O_RDONLY | O_NONBLOCK)
			except OSError:
				logger.debug(f"Unable to open '{softsynth_path}' in read-only mode.")
				raise

	def poll_for_read(self, *, timeout: float | None = None) -> bool:
		"""
		Poll for readability using epoll.

		Args:
			timeout: Seconds to wait, None for blocking.

		Returns:
			True if readable, False otherwise.
		"""
		if self.fd is None or self._epoll is None:
			return False
		events = self._epoll.poll(timeout)
		return len(events) > 0

	def read(self, size: int) -> bytes:
		"""
		Read bytes from the softsynth device.

		Args:
			size: Max bytes to read.

		Returns:
			Read data or empty bytes if closed.
		"""
		if self.fd is None:
			return b""
		return os.read(self.fd, size)

	def write(self, data: bytes) -> None:
		"""
		Write index mark to softsynth.

		Args:
			data: Index mark (should be numeric).
		"""
		if self.fd is None:
			return
		if not data.isdigit():
			logger.warning(f"Speech Dispatcher tried to send non-numeric index mark ({data!r}) to Speakup.")
			return
		with suppress(OSError):
			os.write(self.fd, data)


class Settings:
	"""Settings for the speech bridge."""

	def __init__(self, callback: SettingsCallbackType, *, config_path: Path | None = None) -> None:
		"""
		Initialize settings.

		Args:
			callback: Callback to fire when values change.
			config_path: Path to a settings configuration file.
		"""
		self._callback: SettingsCallbackType = callback
		self._config_path: Path | None = config_path
		self._data_mode: str = speechd.DataMode.SSML
		self._rate: int = 2
		self._pitch: int = 5
		self._volume: int = 5
		self._punctuation: int = 1
		self._pause: bool = False
		self._language: str | None = None
		self._module: str | None = None
		self._voice: str | None = None

	@property
	def data_mode(self) -> str:
		"""Current data mode used for speech (SSML or TEXT)."""
		return self._data_mode

	@data_mode.setter
	def data_mode(self, value: str) -> None:
		self._data_mode = value
		logger.debug(f"Data mode: {value}.")
		self._callback("set_data_mode", value)

	@property
	def pause(self) -> bool:
		"""Whether speech is currently paused."""
		return self._pause

	@pause.setter
	def pause(self, value: bool) -> None:
		self._pause = value
		func: str = "pause" if value else "resume"
		logger.debug(f"{func}.")
		self._callback(func)

	@property
	def pitch(self) -> int:
		"""Current pitch setting (Speakup scale)."""
		return self._pitch

	@pitch.setter
	def pitch(self, value: int) -> None:
		self._pitch = value
		value = (value - 5) * (20 if value < 5 else 25)  # NOQA: PLR2004
		value = clamp(value, -100, 100)
		logger.debug(f"Pitch: {value}.")
		self._callback("set_pitch", value)

	@property
	def punctuation(self) -> int:
		"""Current punctuation level."""
		return self._punctuation

	@punctuation.setter
	def punctuation(self, value: int) -> None:
		self._punctuation = value
		punctuation_mode = PUNCTUATION_MODES[clamp(value, 0, len(PUNCTUATION_MODES) - 1)]
		logger.debug(f"Punctuation: {punctuation_mode}.")
		self._callback("set_punctuation", punctuation_mode)

	@property
	def rate(self) -> int:
		"""Current speech rate setting (Speakup scale)."""
		return self._rate

	@rate.setter
	def rate(self, value: int) -> None:
		self._rate = value
		value = int(value * 22.3) - 100
		value = clamp(value, -100, 100)
		logger.debug(f"Rate: {value}.")
		self._callback("set_rate", value)

	@property
	def volume(self) -> int:
		"""Current volume setting (Speakup scale)."""
		return self._volume

	@volume.setter
	def volume(self, value: int) -> None:
		self._volume = value
		value = (value - 5) * (20 if value < 5 else 25)  # NOQA: PLR2004
		value = clamp(value, -100, 100)
		logger.debug(f"Volume: {value}.")
		self._callback("set_volume", value)

	@property
	def language(self) -> str | None:
		"""Current language setting (Speech Dispatcher)."""
		return self._language

	@language.setter
	def language(self, value: str | None) -> None:
		self._language = value
		logger.debug(f"Language: {value}.")
		if value:
			self._callback("set_language", value)

	@property
	def module(self) -> str | None:
		"""Current output module name (Speech Dispatcher)."""
		return self._module

	@module.setter
	def module(self, value: str | None) -> None:
		self._module = value
		logger.debug(f"Module: {value}.")
		if value:
			self._callback("set_output_module", value)

	@property
	def voice(self) -> str | None:
		"""Current synthesis voice name (Speech Dispatcher)."""
		return self._voice

	@voice.setter
	def voice(self, value: str | None) -> None:
		self._voice = value
		logger.debug(f"Voice: {value}.")
		if value:
			self._callback("set_synthesis_voice", value)

	def init_speech(self) -> None:
		"""Apply stored speech settings to the Speech Dispatcher connection."""
		self.language = self._language
		self.module = self._module
		self.voice = self._voice
		self.data_mode = self._data_mode
		self.rate = self._rate
		self.pitch = self._pitch
		self.volume = self._volume
		self.punctuation = self._punctuation
		self.pause = self._pause

	def load_config(self) -> None:
		"""Load values from configuration file."""
		if self._config_path is None:
			logger.warning("Unable to load configuration file; configuration undefined.")
			return
		if not self._config_path.exists():
			logger.warning(f"Configuration file '{self._config_path}' does not exist.")
			return
		config = configparser.ConfigParser()
		config.read(self._config_path)
		if "speech-dispatcher" in config:
			section = config["speech-dispatcher"]
			if "language" in section:
				self._language = section.get("language")
			if "module" in section:
				self._module = section.get("module")
			if "voice" in section:
				self._voice = section.get("voice")
		else:
			logger.debug(f"No [speech-dispatcher] section found in config file: {self._config_path}")


class ParseState(Enum):
	"""Possible states of the Speakup softsynth protocol parser."""

	TEXT = auto()
	CMD_START = auto()
	SIGN = auto()
	PARAM = auto()


class Sign(IntEnum):
	"""Possible sign indicators of a speech parameter."""

	MINUS = -1
	ZERO = 0
	PLUS = 1


class SpeakupParser:
	"""Stateful parser and bridge between Speakup softsynth protocol and Speech Dispatcher."""

	def __init__(self, *, config_path: Path | None = None) -> None:
		"""
		Initialize parser with default state.

		Args:
			config_path: Path to a settings configuration file.
		"""
		self.connection: SSIPClientType | None = None
		self.softsynth: Softsynth = Softsynth()
		self.settings: Settings = Settings(self.settings_callback, config_path=config_path)
		self._utf8_decoder: IncrementalDecoder = getincrementaldecoder(UTF8)(errors="replace")
		self._is_speaking: bool = False
		self._state: ParseState = ParseState.TEXT
		self._pending_text: bytearray = bytearray()
		self._ssml_parts: list[str] = []
		self._sign: Sign = Sign.ZERO
		self._param: int = 0

	def __del__(self) -> None:
		"""Ensure cleanup on deletion."""
		self.close()

	def __enter__(self) -> Self:
		"""
		Return self for use as context manager.

		Returns:
			Self for use in the 'with' statement.
		"""
		return self

	def __exit__(
		self,
		exc_type: type[BaseException] | None,
		exc_value: BaseException | None,
		exc_traceback: TracebackType | None,
	) -> None:
		"""
		Clean up resources on context exit.

		Args:
			exc_type: Exception type if one was raised, else None.
			exc_value: Exception value if one was raised, else None.
			exc_traceback: Traceback if an exception was raised, else None.
		"""
		self.close()

	def connect(self) -> None:
		"""Open softsynth device, connect to Speech Dispatcher, and apply speech settings."""
		self.open_softsynth()
		self.connect_speech_dispatcher()
		self.settings.load_config()
		self.settings.init_speech()

	def open_softsynth(self) -> None:
		"""Open the Speakup softsynth device."""
		# Attempt to open softsynth device once per second.
		# This allows speech to automatically start after the speakup_soft kernel module is loaded.
		while True:
			with suppress(OSError):
				self.softsynth.open()
			if self.softsynth.fd is not None:
				break
			time.sleep(1)

	def connect_speech_dispatcher(self) -> None:
		"""Connect to Speech Dispatcher."""
		# Attempt to connect to Speech Dispatcher once per second.
		while True:
			with suppress(Exception):
				self.connection = speechd.SSIPClient("speakup", "softsynth", "root")
				logger.debug("Connected to Speech Dispatcher.")
				break
			time.sleep(1)

	def close(self) -> None:
		"""Close Speech Dispatcher connection and softsynth device, reset state."""
		self._reset_state()
		if self.connection is not None:
			with suppress(Exception):
				self.connection.close()
			self.connection = None
		self.softsynth.close()

	def _reset_state(self) -> None:
		"""Reset parser state machine, decoder and buffers."""
		self._utf8_decoder.reset()
		self._pending_text.clear()
		self._ssml_parts.clear()
		self._sign = Sign.ZERO
		self._param = 0
		self._state = ParseState.TEXT

	def sd_callback(self, event_type: str, *, index_mark: str | None = None) -> None:
		"""
		Handle callbacks from Speech Dispatcher.

		Args:
			event_type: Event type from speechd.CallbackType.
			index_mark: Index mark for INDEX_MARK events.
		"""
		if event_type == speechd.CallbackType.INDEX_MARK and index_mark is not None:
			self.softsynth.write(bytes(index_mark, "ascii", errors="replace"))
		elif event_type == speechd.CallbackType.BEGIN:
			self._is_speaking = True
			logger.debug("Speech begin.")
		elif event_type == speechd.CallbackType.END:
			self._is_speaking = False
			logger.debug("Speech end.")

	def settings_callback(self, func_name: str, *args: Any, **kwargs: Any) -> None:
		"""
		Handle value changed callbacks from Settings.

		Args:
			func_name: Name of matching method belonging to active SSIPClient.
			*args: Positional arguments to pass to method.
			**kwargs: Keyword-only arguments to pass to method.
		"""
		if self.connection is not None:
			func = getattr(self.connection, func_name, None)
			if callable(func):
				func(*args, **kwargs)

	def list_modules(self) -> tuple[str, ...]:
		"""
		Current list of available output modules from Speech Dispatcher.

		Returns:
			All output modules as a tuple of strings.
		"""
		return self.connection.list_output_modules() if self.connection is not None else ()

	def list_voices(self, language: str | None = None, variant: str | None = None) -> ListVoicesType:
		"""
		Current list of available voices from Speech Dispatcher.

		Args:
			language: Filter by language.
			variant: Filter by variant.

		Returns:
			A tuple of tripplets (name, language, variant).
		"""
		return self.connection.list_synthesis_voices(language, variant) if self.connection is not None else ()

	@property
	def is_speaking(self) -> bool:
		"""True if currently speaking, False otherwise."""
		return self._is_speaking

	def feed(self, data: bytes) -> None:
		"""
		Parse incoming bytes from softsynth and dispatch text or commands.

		Args:
			data: Raw bytes from softsynth.
		"""
		# skip single-byte parsing if not in command and no commands in data.
		if self._state is ParseState.TEXT and find_any(data, DTLK_CONTROL_ORDINALS) == -1:
			self._pending_text.extend(data)
			self._flush_pending_text()
			self._flush_ssml()
			return
		for byte in iter_bytes(data):
			if self._state is ParseState.TEXT:
				self._handle_text_state(byte)
			elif self._state is ParseState.CMD_START:  # Just saw ^A.
				self._handle_cmd_start_state(byte)
			elif self._state is ParseState.SIGN:  # Saw + or -.
				self._handle_sign_state(byte)
			elif self._state is ParseState.PARAM:  # Collecting digits.
				self._handle_param_state(byte)
		if self._state is ParseState.TEXT:  # Only flush if we are not in the middle of a split command.
			self._flush_pending_text()
			self._flush_ssml()

	def _flush_pending_text(self) -> None:
		"""Flush accumulated bytes as escaped text or character SSML."""
		if not self._pending_text:
			return
		text: str
		if self.softsynth.encoding == UTF8:
			text = self._utf8_decoder.decode(self._pending_text, final=False)
		else:  # Latin-1.
			text = str(self._pending_text, self.softsynth.encoding, errors="replace")
		self._pending_text.clear()
		if len(text) == 1 and not text.isspace() and text.isprintable():
			if self.connection is not None and not self._ssml_parts:
				try:
					self.connection.char(text)
				except Exception:
					logger.exception("SSIP char command failed.")
					# Note that we intentionally fall through to
					# interpret as characters since the call to char failed.
				else:
					return  # Success, don't fall through.
			# We end up here if the call to char failed
			# or if the single character was preceded by an index mark.
			self._ssml_parts.append(f'<say-as interpret-as="characters">{ssml_escape_text(text)}</say-as>')
		elif text:
			self._ssml_parts.append(ssml_escape_text(text))

	def _flush_ssml(self) -> None:
		"""Send any accumulated SSML to Speech Dispatcher."""
		if not self._ssml_parts or self.connection is None:
			return
		raw_ssml = f"<speak>{''.join(self._ssml_parts)}</speak>"
		self._ssml_parts.clear()
		logger.debug(f"Sending SSML with raw marks: {raw_ssml!r}.")
		try:
			self.connection.speak(
				raw_ssml,
				callback=self.sd_callback,
				event_types=(
					speechd.CallbackType.INDEX_MARK,
					speechd.CallbackType.BEGIN,
					speechd.CallbackType.END,
				),
			)
		except Exception:  # pragma: no cover
			logger.exception("Speak SSML failed.")

	def _handle_text_state(self, byte: bytes) -> None:
		"""
		Process byte while in normal text state.

		Args:
			byte: Byte to process.
		"""
		if byte == DTLK_STOP:
			logger.debug("Cancel speech.")
			if self.connection is not None:
				self.connection.cancel()
			self._reset_state()
		elif byte == DTLK_CMD:
			self._sign = Sign.ZERO
			self._param = 0
			self._state = ParseState.CMD_START
		else:
			self._pending_text.extend(byte)

	def _handle_cmd_start_state(self, byte: bytes) -> None:
		"""
		Handle state immediately after receiving command start (^A).

		Args:
			byte: Byte to process.
		"""
		if byte == b"+":
			self._sign = Sign.PLUS
			self._state = ParseState.SIGN
		elif byte == b"-":
			self._sign = Sign.MINUS
			self._state = ParseState.SIGN
		elif byte.isdigit():
			self._param = int(byte)
			self._state = ParseState.PARAM
		else:
			# Bare command with no param.
			self._handle_command(byte, 0, Sign.ZERO)
			self._state = ParseState.TEXT

	def _handle_sign_state(self, byte: bytes) -> None:
		"""
		Handle state after + or - sign in command.

		Args:
			byte: Byte to process.
		"""
		if byte.isdigit():
			self._param = int(byte)
			self._state = ParseState.PARAM
		else:
			# Sign without digits.
			self._handle_command(byte, 0, self._sign)
			self._state = ParseState.TEXT

	def _handle_param_state(self, byte: bytes) -> None:
		"""
		Handle state while collecting parameter digits.

		Args:
			byte: Byte to process.
		"""
		if byte.isdigit():
			self._param = self._param * 10 + int(byte)
		else:
			# Command letter after digits.
			self._handle_command(byte, self._param, self._sign)
			self._state = ParseState.TEXT

	def _handle_command(self, command: bytes, param: int, sign: Sign) -> None:
		"""
		Dispatch fully parsed Speakup command.

		Args:
			command: Command byte.
			param: Parameter value.
			sign: Sign indicator.
		"""
		name = KNOWN_SOFTSYNTH_COMMANDS.get(command, str(command, "ascii"))
		value = f"{'-' if sign < 0 else '+' if sign > 0 else ''}{param}"
		logger.debug(f"CMD: {name!r}, Value: {value}.")
		self._flush_pending_text()
		if command == b"i":
			# Insert RAW unescaped mark.
			self._ssml_parts.append(f'<mark name="{param}"/>')
			# We must not flush SSML if command is an index mark in order to
			# keep it inside the same utterance.
			return
		self._flush_ssml()
		if command == b"@":  # Reset.
			logger.debug("Resetting Speech Dispatcher connection.")
			self.close()
			self.connect()
		elif command == b"b":  # Punctuation.
			self.settings.punctuation = param
		elif command == b"P":  # Pause.
			self.settings.pause = not self.settings.pause
		elif command == b"p":  # Pitch.
			self.settings.pitch = param if sign is Sign.ZERO else self.settings.pitch + sign * param
		elif command == b"s":  # Rate.
			self.settings.rate = param if sign is Sign.ZERO else self.settings.rate + sign * param
		elif command == b"v":  # Volume.
			self.settings.volume = param if sign is Sign.ZERO else self.settings.volume + sign * param

	def run(self) -> None:
		"""Main event loop that reads from softsynth and feeds data to parser."""
		logger.info("Starting speech bridge.")
		self.connect()
		while True:
			try:
				if self.softsynth.poll_for_read():  # Blocks until data is ready.
					data = self.softsynth.read(BLOCK_SIZE)
					if not data:
						break
					self.feed(data)
			except KeyboardInterrupt:
				break
			except InterruptedError:
				continue
			except OSError:
				logger.exception("Select/read error.")
				break
			except Exception:
				logger.exception("Unexpected error in run loop.")
				break
		logger.info("Speech bridge terminated.")


def run() -> None:  # pragma: no cover
	"""Parse arguments and start the Speakup to Speech Dispatcher bridge."""
	parser = argparse.ArgumentParser(description="Speakup Speech Dispatcher bridge")
	parser.add_argument("-c", "--config", metavar="FILE", type=Path, help="path to configuration INI file")
	parser.add_argument(
		"-lm", "--list-modules", action="store_true", help="list available output modules and exit"
	)
	parser.add_argument(
		"-lv",
		"--list-voices",
		nargs="?",
		default=False,
		const=None,
		metavar="LANGUAGE",
		help="list available synthesis voices (optionally filtered by language) and exit",
	)
	verbosity_group = parser.add_mutually_exclusive_group(required=False)
	verbosity_group.add_argument("-d", "--debug", action="store_true", help="show debug messages")
	verbosity_group.add_argument("-q", "--quiet", action="store_true", help="only show warnings and errors")
	args: argparse.Namespace = parser.parse_args()
	if args.debug:
		log_level = logging.DEBUG
	elif args.quiet:
		log_level = logging.WARNING
	else:
		log_level = logging.INFO
	logging.basicConfig(
		level=log_level,
		format="{levelname}: {message}",
		style="{",
	)
	# Explicitly install default SIGINT handler; non-interactive shells
	# set ignore for background jobs, so Python skips auto-install at startup.
	# Fixes KeyboardInterrupt not being thrown when running in background.
	signal.signal(signal.SIGINT, signal.default_int_handler)
	with SpeakupParser(config_path=args.config) as speakup_parser:
		if args.list_modules:
			speakup_parser.connect_speech_dispatcher()
			modules = speakup_parser.list_modules()
			print("Available output modules:")
			print("\n".join(modules))
		elif args.list_voices is not False:
			speakup_parser.connect_speech_dispatcher()
			voices = speakup_parser.list_voices(language=args.list_voices)
			print("Available synthesis voices:")
			print("\n".join(name for name, _, _ in voices))
		else:
			speakup_parser.run()


if __name__ == "__main__":
	run()
