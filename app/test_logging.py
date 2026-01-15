from app.logging_config import setup_logger

logger = setup_logger()

logger.info(
    "test_log",
    extra={
        "extra": {
            "timestamp": "2026-01-14T10:00:00Z",
            "service_name": "soc-analyst-api",
            "environment": "test",
            "endpoint": "/test",
            "http_method": "GET",
            "status_code": 200,
            "latency_ms": 10,
            "request_id": "test-req",
            "trace_id": "test-trace",
            "client_ip": "127.0.0.1",
            "user_agent": "curl",
            "request_size_bytes": 0,
            "response_size_bytes": 32,
            "error_type": None,
            "error_message": None,
        }
    },
)

