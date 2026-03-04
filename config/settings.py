"""
Configuration settings for the Autonomous SOC Analyst
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Elasticsearch
    ELASTICSEARCH_HOST: str = "http://localhost:9200"
    # Base index name for writing
    ELASTICSEARCH_INDEX_LOGS: str = "soc-logs"
    # Pattern for reading (matches Logstash-format indices: soc-logs-YYYY.MM.DD)
    ELASTICSEARCH_INDEX_LOGS_PATTERN: str = "soc-logs*"
    ELASTICSEARCH_INDEX_ANOMALIES: str = "soc-anomalies"
    ELASTICSEARCH_INDEX_INCIDENTS: str = "soc-incidents"
    ELASTICSEARCH_INDEX_METRICS: str = "soc-metrics"

    # Groq API
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # JWT Authentication
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-super-secret-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # ML Settings
    ANOMALY_CONTAMINATION: float = 0.1
    ANOMALY_WINDOW_MINUTES: int = 5
    FEATURE_WINDOW_SIZE: int = 100

    # API Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Log Generator Settings
    LOG_OUTPUT_PATH: str = "logs/app.log"
    LOG_RATE_PER_SECOND: int = 10

    # Agent Settings - Autonomous Mode
    HUMAN_IN_LOOP_ENABLED: bool = False  # Disabled for autonomous operation
    AUTO_APPROVE_LOW_SEVERITY: bool = True  # Auto-approve low severity
    AUTONOMOUS_MODE: bool = True  # Enable fully autonomous decision making
    AUTO_APPROVE_CONFIDENCE_THRESHOLD: float = 0.75  # Auto-approve if confidence >= this
    LEARNING_ENABLED: bool = True  # Enable learning from outcomes

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
