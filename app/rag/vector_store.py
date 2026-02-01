# app/rag/vector_store.py
"""
Vector store singleton for managing PDF processor instance.

Uses FAISS for vector storage with per-user isolation.
"""

from app.rag.pdf_processor import PDFProcessor
from app.config import get_settings
from app.logg import logger

settings = get_settings()

# Singleton instance
_pdf_processor = None


def get_pdf_processor() -> PDFProcessor:
    """
    Get or create the PDF processor singleton.
    
    Returns the same PDFProcessor instance for all calls,
    ensuring efficient resource usage across the application.
    
    Returns:
        PDFProcessor: Singleton instance configured with FAISS persistence
    """
    global _pdf_processor
    
    if _pdf_processor is None:
        logger.info("🔧 Creating PDF Processor singleton...")
        
        # Use FAISS_PERSIST_DIRECTORY from settings (not CHROMA)
        persist_dir = getattr(settings, 'FAISS_PERSIST_DIRECTORY', './faiss_db')
        
        _pdf_processor = PDFProcessor(persist_directory=persist_dir)
        
        logger.info(f"✅ PDF Processor created")
        logger.info(f"   Persist directory: {persist_dir}")
        logger.info(f"   Embedding model: sentence-transformers/all-mpnet-base-v2")
    else:
        logger.debug("♻️  Reusing existing PDF Processor instance")
    
    return _pdf_processor


def reset_pdf_processor():
    """
    Reset the PDF processor singleton.
    
    Useful for:
    - Testing
    - Configuration changes
    - Memory cleanup
    """
    global _pdf_processor
    
    if _pdf_processor is not None:
        logger.info("🔄 Resetting PDF Processor singleton")
        _pdf_processor = None