# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

"""Use Quod Libet's isolated test environment with this repository's plugin."""

import os
from pathlib import Path
import sys

import pytest

source_dir = os.environ.get("QUODLIBET_SOURCE_DIR")
if not source_dir:
    raise pytest.UsageError(
        "Set QUODLIBET_SOURCE_DIR to a Quod Libet source checkout (including tests)."
    )
source_path = Path(source_dir).expanduser().resolve()
if (
    not (source_path / "quodlibet/__init__.py").is_file()
    or not (source_path / "tests/__init__.py").is_file()
):
    raise pytest.UsageError("QUODLIBET_SOURCE_DIR must contain quodlibet/ and tests/.")

sys.path.insert(0, str(source_path))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Importing upstream's tests initializes GTK, temporary user data and a test
# D-Bus session. Its hooks also turn GTK callback exceptions into test failures.
pytest_plugins = ["tests.conftest"]
