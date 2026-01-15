import logging
import json
from datetime import datetime


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "@timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
        }

        if hasattr(record, "extra"):
            log_record.update(record.extra)

        return json.dumps(log_record)


def setup_logger():
    logger = logging.getLogger("soc-logger")
    logger.setLevel(logging.INFO)

    handler = logging.FileHandler("logs/app.log")
    handler.setFormatter(JsonFormatter())

    logger.addHandler(handler)
    logger.propagate = False
    return logger

