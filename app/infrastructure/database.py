# app/infrastructure/database.py
from typing import Tuple
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from app.config import get_settings
from app.logg import logger


class DatabaseResources:
    """
    Context manager for PostgreSQL checkpointer and store.
    
    Usage:
        with DatabaseResources() as (checkpointer, store):
            graph = builder.build(checkpointer, store)
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.checkpointer_cm = None
        self.store_cm = None
        self.checkpointer = None
        self.store = None
    
    def __enter__(self) -> Tuple[PostgresSaver, PostgresStore]:
        """Enter the context - setup database resources."""
        logger.info("🔧 Initializing DatabaseResources...")
        
        try:
            # Create context managers
            logger.info("📊 Creating PostgresSaver connection...")
            self.checkpointer_cm = PostgresSaver.from_conn_string(
                self.settings.DATABASE_URL
            )
            
            logger.info("📊 Creating PostgresStore connection...")
            self.store_cm = PostgresStore.from_conn_string(
                self.settings.DATABASE_URL
            )
            
            # Enter contexts
            logger.info("🔗 Entering PostgresSaver context...")
            self.checkpointer = self.checkpointer_cm.__enter__()
            
            logger.info("🔗 Entering PostgresStore context...")
            self.store = self.store_cm.__enter__()
            
            # Setup tables
            logger.info("🗄️  Setting up checkpointer tables...")
            self.checkpointer.setup()
            
            logger.info("🗄️  Setting up store tables...")
            self.store.setup()
            
            logger.info("✅ DatabaseResources initialized successfully")
            
            return self.checkpointer, self.store
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize DatabaseResources: {e}")
            # Cleanup any partial initialization
            self.__exit__(type(e), e, e.__traceback__)
            raise
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context - cleanup database resources."""
        logger.info("🧹 Cleaning up DatabaseResources...")
        
        # Cleanup in reverse order
        if self.store_cm:
            try:
                logger.info("🔌 Closing PostgresStore connection...")
                self.store_cm.__exit__(exc_type, exc_val, exc_tb)
                logger.info("✅ PostgresStore connection closed")
            except Exception as e:
                logger.error(f"⚠️  Error closing store: {e}")
        
        if self.checkpointer_cm:
            try:
                logger.info("🔌 Closing PostgresSaver connection...")
                self.checkpointer_cm.__exit__(exc_type, exc_val, exc_tb)
                logger.info("✅ PostgresSaver connection closed")
            except Exception as e:
                logger.error(f"⚠️  Error closing checkpointer: {e}")
        
        # Don't suppress exceptions
        return False


# Optional: Keep a helper function for testing
def get_database_resources() -> DatabaseResources:
    """Helper function to get DatabaseResources instance."""
    return DatabaseResources()