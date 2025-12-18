"""
Application configuration settings.
Centralized config - reads from environment variables.
"""
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # App metadata
    app_name: str = "connect4-backend"
    app_version: str = "1.0.0"

    # API Configuration
    debug: bool = False

    # CORS - Allow both frontend ports (5173=platform, 5174=connect4)
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:5174"]
    cors_credentials: bool = True
    cors_methods: List[str] = ["*"]
    cors_headers: List[str] = ["*"]

    # PostgreSQL Configuration
    # Environment variables: POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
    postgres_host: str = "platform_postgres"
    postgres_port: int = 5432
    postgres_db: str = "postgres"
    postgres_user: str = "user"
    postgres_password: str = "password"

    # Database connection pool settings
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_echo: bool = False  # Set to True to log SQL queries

    @property
    def database_url(self) -> str:
        """PostgreSQL connection URL for SQLAlchemy."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_safe(self) -> str:
        """PostgreSQL connection URL without password (for logging)."""
        return (
            f"postgresql://{self.postgres_user}:****"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # RabbitMQ Configuration
    # Environment variables: RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USER, RABBITMQ_PASSWORD
    rabbitmq_host: str = "rabbitmq"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "user"
    rabbitmq_password: str = "password"

    @property
    def rabbitmq_url(self) -> str:
        return (
            f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}"
            f"@{self.rabbitmq_host}:{self.rabbitmq_port}/"
        )

    # Logging Configuration
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False  # Allows POSTGRES_HOST to match postgres_host


settings = Settings()
