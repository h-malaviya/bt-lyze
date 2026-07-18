import json
import logging
from pathlib import Path

import structlog

from api.app.config import Settings
from api.app.logging import configure_logging


def test_structured_logs_write_to_terminal_and_rotating_file(tmp_path: Path) -> None:
    log_file = tmp_path / "application.log"
    settings = Settings(
        log_file=str(log_file),
        log_level="INFO",
        log_max_bytes=1024 * 1024,
        log_backup_count=2,
    )
    configure_logging(settings, "test-service")

    structlog.get_logger("logging-test").info(
        "pipeline_test_event",
        recording_id="recording-123",
    )
    for handler in logging.getLogger().handlers:
        handler.flush()

    entries = [json.loads(line) for line in log_file.read_text("utf-8").splitlines()]
    assert entries[-1]["event"] == "pipeline_test_event"
    assert entries[-1]["service"] == "test-service"
    assert entries[-1]["recording_id"] == "recording-123"
    assert entries[-1]["level"] == "info"

    for handler in logging.getLogger().handlers:
        handler.close()
    logging.getLogger().handlers.clear()
