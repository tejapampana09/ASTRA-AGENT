import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class StructuredJsonFormatter(logging.Formatter):
    """
    Format logs as JSON objects with timestamp, severity, component, task_id, and message.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include custom task or trace metadata if attached
        if hasattr(record, "task_id") and record.task_id:
            log_obj["task_id"] = record.task_id
        if hasattr(record, "component") and record.component:
            log_obj["component"] = record.component
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def setup_logger(name: str = "astra", level: str = "INFO", json_format: bool = False) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not logger.handlers:
        import os
        from pathlib import Path
        if os.environ.get("ASTRA_CLI_MODE") == "1":
            log_file = Path.cwd() / "astra_agent.log"
            handler = logging.FileHandler(str(log_file), encoding="utf-8")
        else:
            handler = logging.StreamHandler(sys.stdout)

        if json_format:
            handler.setFormatter(StructuredJsonFormatter())
        else:
            handler.setFormatter(
                logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
            )
        logger.addHandler(handler)

    logger.propagate = False
    return logger


# Default logger instance
logger = setup_logger()
