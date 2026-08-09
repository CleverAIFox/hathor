"""환경 설정. 자격증명은 코드에 넣지 않는다 (GR-5 / §5.5)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    redis_url: str
    amqp_url: str
    mongo_url: str
    s3_endpoint_url: str

    @staticmethod
    def from_env() -> Settings:
        return Settings(
            database_url=os.environ.get(
                "DATABASE_URL", "postgresql://hathor:hathor@localhost:5432/hathor"
            ),
            redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
            amqp_url=os.environ.get("AMQP_URL", "amqp://hathor:hathor@localhost:5672//"),
            mongo_url=os.environ.get(
                "MONGO_URL", "mongodb://hathor:hathor@localhost:27017/hathor?authSource=admin"
            ),
            s3_endpoint_url=os.environ.get("S3_ENDPOINT_URL", "http://localhost:9000"),
        )
