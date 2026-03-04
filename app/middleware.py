import time
import uuid
from fastapi import Request


async def logging_middleware(request: Request, call_next, logger):
    start_time = time.time()
    request_id = str(uuid.uuid4())
    trace_id = request.headers.get("X-Trace-Id", request_id)

    try:
        response = await call_next(request)
        status_code = response.status_code
        error_type = None
        error_message = None
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError) as e:
        # Client disconnected during response - this is expected behavior
        # Don't treat as an error, just log at debug level and return gracefully
        logger.debug(
            f"Client disconnected during request: {type(e).__name__}",
            extra={"extra": {"request_id": request_id, "endpoint": request.url.path}}
        )
        # Return None to signal the connection was closed
        return None
    except Exception as e:
        response = None
        status_code = 500
        error_type = type(e).__name__
        error_message = str(e)

        from fastapi.responses import JSONResponse
        response = JSONResponse(
            content={"status": "fail", "error": error_message},
            status_code=500,
        )

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
                "status_code": status_code,
                "latency_ms": latency_ms,
                "request_id": request_id,
                "trace_id": trace_id,
                "client_ip": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", ""),
                "request_size_bytes": int(request.headers.get("content-length", 0)),
                "response_size_bytes": int(response.headers.get("content-length", 0)) if response else 0,
                "error_type": error_type,
                "error_message": error_message,
            }
        },
    )

    return response

