-- P0: 확장 설치와 부속 DB 생성만 한다. 스키마는 P1에서 Alembic으로 관리한다.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE DATABASE mlflow;
CREATE DATABASE prefect;
