from fastapi import FastAPI, Request
from middleware import logging_middleware
from logging_config import setup_logger
 

app = FastAPI()
logger = setup_logger()

@app.middleware("http")
async def log_requests(request: Request, call_next):
    return await logging_middleware(request, call_next, logger)


@app.get("/health")
async def health():
    return {
            "status": "ok"
    }

@app.get("/fail")
def fail():
    
    raise ValueError("forced error for testing")
