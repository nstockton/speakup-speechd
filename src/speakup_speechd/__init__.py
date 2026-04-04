# Copyright (C) 2026 Nick Stockton
# SPDX-License-Identifier: GPL-2.0-only
# This program is free software; you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation; version 2 of the License.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# file `LICENSE` for more details.

"""Package initialization."""

# Future Modules:
from __future__ import annotations

# Built-in Modules:
from contextlib import suppress
from typing import TYPE_CHECKING


__version__: str = "0.0.0"
if not TYPE_CHECKING:
	with suppress(ImportError):
		from ._version import __version__


__all__: list[str] = [
	"__version__",
]
