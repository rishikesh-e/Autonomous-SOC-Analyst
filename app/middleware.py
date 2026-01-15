import time
import uuid
from fastapi import Request


async def logging_middleware(request: Request, call_next, logger):
    start_time = time.time()

    request_id = str(uuid.uuid4())
    trace_id = request.headers.get("X-Trace-Id", request_id)

    response = await call_next(request)
    latency_ms = int((time.time() - start_time) * 1000)

    logger.info(
        "request_completed",
        extra={
            "extra": {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "service_name": "soc-analyst-api",
                "environment": "dev",
                "endpoint": request.url.path,
                "http_method": request.method,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
                "request_id": request_id,
                "trace_id": trace_id,
                "client_ip": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", ""),
                "request_size_bytes": int(request.headers.get("content-length", 0)),
                "response_size_bytes": int(response.headers.get("content-length", 0)),
                "error_type": None,
                "error_message": None,
            }
        },
    )

    return response

