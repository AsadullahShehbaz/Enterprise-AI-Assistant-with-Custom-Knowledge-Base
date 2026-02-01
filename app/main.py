# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import get_settings
from app.database import init_db
from app.routers import auth, chat, documents
from app.agents.chatbot import get_chatbot_agent, cleanup_chatbot_agent
from app.logg import logger

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles:
    - Database initialization
    - ChatbotAgent initialization (with DatabaseResources)
    - Cleanup on shutdown
    """
    
    # --------------------------
    # 🚀 STARTUP
    # --------------------------
    logger.info("=" * 60)
    logger.info(f"🚀 Starting {settings.APP_NAME}...")
    logger.info("=" * 60)
    
    try:
        # Initialize SQLAlchemy database
        logger.info("🗄️  Initializing SQLAlchemy database...")
        init_db()
        logger.info("✅ Database initialized")
        
        # Initialize ChatbotAgent (this also initializes DatabaseResources)
        logger.info("🤖 Initializing ChatbotAgent...")
        await get_chatbot_agent()
        logger.info("✅ ChatbotAgent ready")
        
        logger.info("=" * 60)
        logger.info(f"✅ {settings.APP_NAME} started successfully!")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise
    
    # Application runs here
    yield
    
    # --------------------------
    # 🛑 SHUTDOWN
    # --------------------------
    logger.info("=" * 60)
    logger.info(f"🛑 Shutting down {settings.APP_NAME}...")
    logger.info("=" * 60)
    
    try:
        # Cleanup ChatbotAgent (this also cleans up DatabaseResources)
        logger.info("🧹 Cleaning up ChatbotAgent...")
        cleanup_chatbot_agent()
        logger.info("✅ ChatbotAgent cleaned up")
        
        logger.info("=" * 60)
        logger.info(f"👋 {settings.APP_NAME} shutdown complete")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"⚠️  Shutdown error: {e}")


# --------------------------
# FastAPI App Configuration
# --------------------------
app = FastAPI(
    title=settings.APP_NAME,
    description="A persistent chatbot with calculator, web search, RAG, and PostgreSQL memory",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(documents.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "docs": "/docs",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )