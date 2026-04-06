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


class SDCallbackType(Protocol):
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

	def speak(
		self,
		text: str,
		callback: SDCallbackType | None = None,
		event_types: Iterable[str] | None = None,
	) -> None: ...

	def char(self, char: bytes | str) -> None: ...

	def cancel(self, scope: str = "self") -> None: ...

	def list_synthesis_voices(
		self, language: str | None = None, variant: str | None = None
	) -> ListVoicesType: ...

	def list_output_modules(self) -> tuple[str, ...]: ...

	def set_output_module(self, name: str, scope: str = "self") -> None: ...

	def close(self) -> None: ...


__all__: list[str] = [
	"ListVoicesType",
	"SDCallbackType",
	"SSIPClientType",
	"Self",
	"SettingsCallbackType",
	"T",
]
