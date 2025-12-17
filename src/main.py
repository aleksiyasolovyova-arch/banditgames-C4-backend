"""
Main FastAPI application.
Sets up dependency injection, middleware, and routes.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import settings

from src.data_access.database import DatabaseConfig
from src.data_access.postgres_game_repository import PostgresGameRepository
from src.data_access import RabbitMQEventPublisher

from src.service.game_service import GameService
from src.service.move_service import MoveService

from src.controller.game_controller import router as game_router
from src.controller.move_controller import router as move_router

# Logging Setup
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format=settings.log_format
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Initializes database, infrastructure, and services.
    """
    logger.info("Starting Connect Four API...")

    try:
        # Test database connection
        if not DatabaseConfig.test_connection():
            raise RuntimeError("Database connection failed")

        logger.info("Database connection established")

        # Infrastructure
        publisher = RabbitMQEventPublisher(settings)

        # Store references for dependency injection
        app.state.db_config = DatabaseConfig
        app.state.event_publisher = publisher

        logger.info("Services initialized")
        logger.info(f"{settings.app_name} v{settings.app_version} started successfully")

    except Exception as e:
        logger.error(f"Failed to start application: {e}", exc_info=True)
        raise

    yield

    logger.info("Shutting down Connect Four API...")

    try:
        # Close RabbitMQ
        pub = getattr(app.state, "event_publisher", None)
        if pub:
            pub.close()
            logger.info("RabbitMQ connection closed")

        # Close database
        DatabaseConfig.close_engine()
        logger.info("Database connection closed")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)

    logger.info("Shutdown complete")


app = FastAPI(
    description="Connect Four Backend",
    lifespan=lifespan
)

# Middleware - CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_credentials,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"{request.method} {request.url.path} - {response.status_code}")
    return response


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health", tags=["health"])
async def health_check(request: Request):
    publisher = getattr(request.app.state, "event_publisher", None)
    rabbitmq_connected = bool(getattr(publisher, "_connection", None)) if publisher else False

    db_connected = DatabaseConfig.test_connection()

    return {
        "status": "healthy" if (db_connected and rabbitmq_connected) else "degraded",
        "service": settings.app_name,
        "version": settings.app_version,
        "database": "connected" if db_connected else "disconnected",
        "rabbitmq": "connected" if rabbitmq_connected else "disconnected"
    }


# Routes
app.include_router(game_router)
app.include_router(move_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )