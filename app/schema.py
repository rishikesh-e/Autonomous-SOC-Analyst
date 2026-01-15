from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class LogEvent(BaseModel):
    timestamp: datetime
    service_name: str
    environment: str

    endpoint: str
    http_method: str
    status_code: int
    latency_ms: int

    request_id: str
    trace_id: str

    client_ip: str
    user_agent: str
    request_size_bytes: int
    response_size_bytes: int

    error_type: Optional[str] = None
    error_message: Optional[str] = None

