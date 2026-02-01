# app/routers/documents.py
"""
Document management endpoints for RAG functionality.

Handles:
- PDF upload and processing
- Document listing
- Document deletion
- Vector store integration
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import tempfile
import os

from app.database import get_db
from app.models import User, Document
from app.auth import get_current_user
from app.rag.vector_store import get_pdf_processor
from app.logg import logger


# ========================== 
# Router Configuration
# ========================== 
router = APIRouter(
    prefix="/api/documents",
    tags=["Documents"]
)


# ========================== 
# Upload PDF Document
# ========================== 
@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload and process a PDF document for RAG.
    
    The document is:
    1. Saved temporarily
    2. Processed in background (chunked, embedded, stored in vector DB)
    3. Metadata saved in database
    """
    logger.info("=" * 60)
    logger.info(f"📤 PDF upload received from user {current_user.id}")
    logger.info(f"   Filename: {file.filename}")
    logger.info(f"   Content-Type: {file.content_type}")
    logger.info("=" * 60)
    
    # Validate file type
    if not file.filename.endswith(".pdf"):
        logger.warning(f"❌ Invalid file type: {file.filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are allowed"
        )
    
    # Check if file already exists for this user
    existing_doc = db.query(Document).filter(
        Document.user_id == current_user.id,
        Document.filename == file.filename
    ).first()
    
    if existing_doc:
        logger.warning(f"⚠️  Document already exists: {file.filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document '{file.filename}' already uploaded"
        )
    
    try:
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        logger.info(f"📊 File size: {file_size / 1024:.2f} KB")
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        
        logger.info(f"💾 Temporary file created: {tmp_path}")
        
        # Create document record in database
        document = Document(
            user_id=current_user.id,
            filename=file.filename,
            file_size=file_size,
            uploaded_at=datetime.utcnow(),
            status="processing"  # Will be updated after processing
        )
        
        db.add(document)
        db.commit()
        db.refresh(document)
        
        logger.info(f"✅ Document record created: ID={document.id}")
        
        # Schedule background processing
        background_tasks.add_task(
            process_pdf_background,
            pdf_path=tmp_path,
            user_id=current_user.id,
            doc_id=document.id,
            filename=file.filename
        )
        
        logger.info(f"⏳ Background processing scheduled for document {document.id}")
        
        return {
            "message": "PDF uploaded successfully and is being processed",
            "document_id": document.id,
            "filename": file.filename,
            "status": "processing"
        }
    
    except Exception as e:
        logger.exception(f"🔥 PDF upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload PDF: {str(e)}"
        )


# ========================== 
# Background Processing Function
# ========================== 
def process_pdf_background(
    pdf_path: str,
    user_id: int,
    doc_id: int,
    filename: str
):
    """
    Process PDF in background: chunk, embed, and store in vector database.
    
    This runs asynchronously after the upload response is sent.
    """
    from app.database import SessionLocal
    
    logger.info("=" * 60)
    logger.info(f"🧠 Starting background PDF processing")
    logger.info(f"   User ID: {user_id}")
    logger.info(f"   Document ID: {doc_id}")
    logger.info(f"   Filename: {filename}")
    logger.info(f"   Path: {pdf_path}")
    logger.info("=" * 60)
    
    db = SessionLocal()
    
    try:
        # Get PDF processor
        pdf_processor = get_pdf_processor()
        logger.info("✅ PDF processor initialized")
        
        # Process the PDF (chunk, embed, store)
        logger.info("📄 Processing PDF content...")
        pdf_processor.process_pdf(
            pdf_path=pdf_path,
            user_id=user_id,
            doc_id=doc_id
        )
        logger.info("✅ PDF processed and embedded successfully")
        
        # Update document status in database
        document = db.query(Document).filter(Document.id == doc_id).first()
        if document:
            document.status = "completed"
            document.processed_at = datetime.utcnow()
            db.commit()
            logger.info(f"✅ Document {doc_id} status updated to 'completed'")
        
        logger.info("=" * 60)
        logger.info(f"🎉 PDF processing complete: {filename}")
        logger.info("=" * 60)
    
    except Exception as e:
        logger.exception(f"🔥 PDF processing failed: {e}")
        
        # Update document status to failed
        try:
            document = db.query(Document).filter(Document.id == doc_id).first()
            if document:
                document.status = "failed"
                document.error_message = str(e)
                db.commit()
                logger.info(f"❌ Document {doc_id} status updated to 'failed'")
        except Exception as db_error:
            logger.error(f"Failed to update document status: {db_error}")
    
    finally:
        # Cleanup: Remove temporary file
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
                logger.info(f"🧹 Temporary file deleted: {pdf_path}")
            except Exception as e:
                logger.error(f"Failed to delete temp file: {e}")
        
        # Close database session
        db.close()


# ========================== 
# List User's Documents
# ========================== 
@router.get("/")
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all documents uploaded by the current user.
    
    Returns list of documents with metadata.
    """
    documents = db.query(Document).filter(
        Document.user_id == current_user.id
    ).order_by(Document.uploaded_at.desc()).all()
    
    logger.info(f"📋 Listed {len(documents)} documents for user {current_user.id}")
    
    return [
        {
            "id": doc.id,
            "filename": doc.filename,
            "file_size": doc.file_size,
            "status": doc.status,
            "uploaded_at": doc.uploaded_at.isoformat(),
            "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
            "error_message": doc.error_message
        }
        for doc in documents
    ]


# ========================== 
# Get Single Document
# ========================== 
@router.get("/{document_id}")
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific document by ID."""
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    return {
        "id": document.id,
        "filename": document.filename,
        "file_size": document.file_size,
        "status": document.status,
        "uploaded_at": document.uploaded_at.isoformat(),
        "processed_at": document.processed_at.isoformat() if document.processed_at else None,
        "error_message": document.error_message
    }


# ========================== 
# Delete Document
# ========================== 
@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a document.
    
    Note: This only deletes the database record.
    Vector embeddings remain in the vector store (which is fine for RAG).
    """
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    filename = document.filename
    
    db.delete(document)
    db.commit()
    
    logger.info(f"🗑️  Deleted document {document_id}: {filename}")
    
    return {
        "message": "Document deleted successfully",
        "filename": filename
    }


# ========================== 
# Get Upload Statistics
# ========================== 
@router.get("/stats/summary")
async def get_upload_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get upload statistics for the current user."""
    from sqlalchemy import func
    
    total_docs = db.query(func.count(Document.id)).filter(
        Document.user_id == current_user.id
    ).scalar()
    
    completed_docs = db.query(func.count(Document.id)).filter(
        Document.user_id == current_user.id,
        Document.status == "completed"
    ).scalar()
    
    processing_docs = db.query(func.count(Document.id)).filter(
        Document.user_id == current_user.id,
        Document.status == "processing"
    ).scalar()
    
    failed_docs = db.query(func.count(Document.id)).filter(
        Document.user_id == current_user.id,
        Document.status == "failed"
    ).scalar()
    
    total_size = db.query(func.sum(Document.file_size)).filter(
        Document.user_id == current_user.id
    ).scalar() or 0
    
    return {
        "total_documents": total_docs,
        "completed": completed_docs,
        "processing": processing_docs,
        "failed": failed_docs,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2)
    }