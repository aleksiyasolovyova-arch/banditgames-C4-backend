"""
Database configuration and connection management.
Provides SQLAlchemy engine and session management.
"""
import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, Engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from ..config import settings

logger = logging.getLogger(__name__)


class DatabaseConfig:
    """
    Database configuration and connection pool manager.
    Singleton pattern for engine management.
    """
    _engine: Engine | None = None
    _session_factory: sessionmaker | None = None

    @classmethod
    def get_engine(cls) -> Engine:
        """
        Get or create the SQLAlchemy engine.
        Uses connection pooling for production performance.
        """
        if cls._engine is None:
            logger.info(f"Creating database engine: {settings.database_url_safe}")

            cls._engine = create_engine(
                settings.database_url,
                poolclass=QueuePool,
                pool_size=settings.db_pool_size,
                max_overflow=settings.db_max_overflow,
                pool_pre_ping=True,  # Verify connections before using
                pool_recycle=3600,   # Recycle connections after 1 hour
                echo=settings.db_echo,  # Log SQL queries if enabled
                # Set schema search path
                connect_args={
                    "options": "-c search_path=connect4_backend,public"
                }
            )

            # Set schema for all connections
            @event.listens_for(cls._engine, "connect")
            def set_search_path(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("SET search_path TO connect4_backend, public")
                cursor.close()

            logger.info("Database engine created successfully")

        return cls._engine

    @classmethod
    def get_session_factory(cls) -> sessionmaker:
        """Get or create the session factory."""
        if cls._session_factory is None:
            engine = cls.get_engine()
            cls._session_factory = sessionmaker(
                bind=engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False
            )

        return cls._session_factory

    @classmethod
    @contextmanager
    def get_session(cls) -> Generator[Session, None, None]:
        """
        Context manager for database sessions.
        Automatically handles commit/rollback and cleanup.

        Usage:
            with DatabaseConfig.get_session() as session:
                session.query(GameEntity).all()
        """
        session_factory = cls.get_session_factory()
        session: Session = session_factory()

        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}", exc_info=True)
            raise
        finally:
            session.close()

    @classmethod
    def close_engine(cls) -> None:
        """Close the database engine and cleanup resources."""
        if cls._engine is not None:
            logger.info("Closing database engine")
            cls._engine.dispose()
            cls._engine = None
            cls._session_factory = None
            logger.info("Database engine closed")

    @classmethod
    def test_connection(cls) -> bool:
        """
        Test database connectivity.
        Returns True if connection successful, False otherwise.
        """
        try:
            from sqlalchemy import text
            engine = cls.get_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database connection test successful")
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False


# Convenience function for dependency injection
def get_db_session() -> Generator[Session, None, None]:
    """
    Dependency injection function for FastAPI.

    Usage:
        @router.get("/games")
        def get_games(session: Session = Depends(get_db_session)):
            ...
    """
    with DatabaseConfig.get_session() as session:
        yield session