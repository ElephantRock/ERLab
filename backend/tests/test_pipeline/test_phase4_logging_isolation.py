"""Phase 4 / 4G — focused regression: alembic fileConfig must not disable loggers.

Root cause of the test_phase3_gap_analysis_diagnosis pollution (proven via
bisect to test_discovery_execution_linkage.py::test_migration_018_*):

  alembic/env.py called logging.config.fileConfig(config_file_name) with the
  default disable_existing_loggers=True. fileConfig() then disabled every
  logger created before the migration ran — including
  backend.pipeline.gap_analysis.gap_analyzer — so caplog could not capture
  that logger's warnings in any test running later in the same session.

The fix: env.py passes disable_existing_loggers=False explicitly (the matching
'disable_existing_loggers = False' key in alembic.ini documents the intent but
Python's fileConfig requires the kwarg in this version).

This regression test proves the leak is closed: running a real alembic
migration must NOT disable a pre-existing logger.
"""

from __future__ import annotations

import logging
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock


def test_alembic_migration_does_not_disable_preexisting_logger():
    """After command.upgrade runs, a logger created before it is still enabled."""
    # Reproduce the import-time sys.modules mocking that the polluting test does
    # (not the cause, but keeps this test self-contained and order-independent).
    sys.modules.setdefault("chromadb", MagicMock())
    sys.modules.setdefault("google.generativeai", MagicMock())

    from unittest.mock import patch

    from alembic.config import Config

    from alembic import command

    project_root = Path(__file__).resolve().parents[3]

    # Create a logger BEFORE running the migration, exactly as gap_analyzer's
    # module-level `logger = logging.getLogger(__name__)` does at import time.
    pre_logger = logging.getLogger("backend.pipeline.gap_analysis.gap_analyzer")
    assert pre_logger.disabled is False, "precondition: logger enabled before migration"

    with tempfile.TemporaryDirectory() as tmp:
        db_url = f"sqlite:///{tmp}/isolation.db"
        cfg = Config(str(project_root / "alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", db_url)

        mock_settings = MagicMock()
        mock_settings.database_url = db_url
        mock_settings.debug = False
        with patch("backend.config.get_settings", return_value=mock_settings):
            # Run a migration — this is where fileConfig() used to disable loggers.
            command.upgrade(cfg, "head")

    # The logger created before the migration must still be enabled.
    assert pre_logger.disabled is False, (
        "alembic fileConfig disabled a pre-existing logger — "
        "env.py must call fileConfig(..., disable_existing_loggers=False)"
    )
