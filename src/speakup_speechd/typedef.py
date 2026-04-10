# Copyright (C) 2026 Nick Stockton
# SPDX-License-Identifier: GPL-2.0-only
# This program is free software; you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation; version 2 of the License.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# file `LICENSE` for more details.

"""Shared type definitions."""

# Future Modules:
from __future__ import annotations

# Built-in Modules:
import sys
from collections.abc import Iterable
from typing import Any, Protocol, TypeAlias, TypeVar


if sys.version_info >= (3, 11):
	from typing import Self
else:
	try:
		from typing_extensions import Self
	except ImportError:
		print("ERROR: typing_extensions Python module not found.", file=sys.stderr)
		raise SystemExit(1) from None


ListVoicesType: TypeAlias = tuple[tuple[str, str | None, str | None], ...]
T = TypeVar("T")


class SettingsCallbackType(Protocol):
	def __call__(self, func_name: str, *args: Any, **kwargs: Any) -> None: ...


class SDEventCallbackType(Protocol):
	def __call__(self, event_type: str, *, index_mark: str | None = None) -> None: ...


class SSIPClientType(Protocol):
	def __init__(
		self,
		name: str,
		component: str = "default",
		user: str = "unknown",
		address: str | None = None,
		autospawn: bool | None = None,
		host: str | None = None,
		port: int | None = None,
		method: str | None = None,
		socket_path: str | None = None,
	) -> None: ...

	def set_priority(self, priority: str) -> None: ...

	def set_data_mode(self, value: str) -> None: ...

	def speak(
		self,
		text: str,
		callback: SDEventCallbackType | None = None,
		event_types: Iterable[str] | None = None,
	) -> tuple[int, str, tuple[str, ...]]: ...

	def char(self, char: str) -> None: ...

	def key(self, key: str) -> None: ...

	def sound_icon(self, sound_icon: str) -> None: ...

	def cancel(self, scope: str | int = "self") -> None: ...

	def stop(self, scope: str | int = "self") -> None: ...

	def pause(self, scope: str | int = "self") -> None: ...

	def resume(self, scope: str | int = "self") -> None: ...

	def list_output_modules(self) -> tuple[str, ...]: ...

	def list_synthesis_voices(
		self, language: str | None = None, variant: str | None = None
	) -> ListVoicesType: ...

	def set_language(self, language: str, scope: str | int = "self") -> None: ...

	def get_language(self) -> str | None: ...

	def set_output_module(self, name: str, scope: str | int = "self") -> None: ...

	def get_output_module(self) -> str | None: ...

	def set_pitch(self, value: int, scope: str | int = "self") -> None: ...

	def get_pitch(self) -> str | None: ...

	def set_pitch_range(self, value: int, scope: str | int = "self") -> None: ...

	def set_rate(self, value: int, scope: str | int = "self") -> None: ...

	def get_rate(self) -> str | None: ...

	def set_volume(self, value: int, scope: str | int = "self") -> None: ...

	def get_volume(self) -> str | None: ...

	def set_punctuation(self, value: str, scope: str | int = "self") -> None: ...

	def get_punctuation(self) -> str | None: ...

	def set_spelling(self, value: bool, scope: str | int = "self") -> None: ...

	def set_cap_let_recogn(self, value: str, scope: str | int = "self") -> None: ...

	def set_voice(self, value: str, scope: str | int = "self") -> None: ...

	def set_synthesis_voice(self, value: str, scope: str | int = "self") -> None: ...

	def set_pause_context(self, value: int, scope: str | int = "self") -> None: ...

	def set_debug(self, val: bool) -> None: ...

	def set_debug_destination(self, path: str) -> None: ...

	def block_begin(self) -> None: ...

	def block_end(self) -> None: ...

	def close(self) -> None: ...


__all__: list[str] = [
	"ListVoicesType",
	"SDEventCallbackType",
	"SSIPClientType",
	"Self",
	"SettingsCallbackType",
	"T",
]
