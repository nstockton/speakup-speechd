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
from typing import Protocol, TypeAlias, TypeVar


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


class EventCallbackType(Protocol):
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

	def set_data_mode(self, value: str) -> None: ...

	def speak(
		self,
		text: str,
		callback: EventCallbackType | None = None,
		event_types: Iterable[str] | None = None,
	) -> None: ...

	def char(self, char: bytes | str) -> None: ...

	def cancel(self, scope: str = "self") -> None: ...

	def pause(self, scope: str = "self") -> None: ...

	def resume(self, scope: str = "self") -> None: ...

	def list_synthesis_voices(
		self, language: str | None = None, variant: str | None = None
	) -> ListVoicesType: ...

	def set_language(self, language: str | None, scope: str = "self") -> None: ...

	def set_pitch(self, value: int, scope: str = "self") -> None: ...

	def set_rate(self, value: int, scope: str = "self") -> None: ...

	def set_volume(self, value: int, scope: str = "self") -> None: ...

	def set_punctuation(self, value: str, scope: str = "self") -> None: ...

	def set_synthesis_voice(self, value: str, scope: str = "self") -> None: ...

	def close(self) -> None: ...


__all__: list[str] = [
	"EventCallbackType",
	"ListVoicesType",
	"SSIPClientType",
	"Self",
	"T",
]
