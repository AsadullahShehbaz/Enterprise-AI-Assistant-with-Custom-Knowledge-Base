# app/routers/chat.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from fastapi.responses import StreamingResponse
import json 
from app.agents import chatbot
from app.database import get_db
from app.models import User, Thread
from app.schemas import ChatRequest, ChatResponse
from app.auth import get_current_user
from app.agents.chatbot import get_chatbot_agent
from app.logg import logger

router = APIRouter(prefix="/api/chat", tags=["Chat"])

@router.post("/stream")  # ← NEW endpoint for streaming
async def chat_stream(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Streaming chat endpoint with real-time response.
    
    Returns Server-Sent Events (SSE) stream.
    """
    logger.info(f"🌊 Stream request | user={current_user.id} | thread={request.thread_id}")
    
    user_id = current_user.id 
    # --------------------------
    # 1. Handle Thread Logic (same as before)
    # --------------------------
    thread_id = request.thread_id
    
    if thread_id:
        thread = (
            db.query(Thread)
            .filter(
                Thread.id == thread_id,
                Thread.user_id == user_id,
            )
            .first()
        )
        if not thread:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thread not found"
            )
        logger.info(f"📝 Using existing thread: {thread_id}")
    else:
        logger.info("🆕 Creating new thread for user")
        thread = Thread(
            user_id=user_id,
            title="New conversation",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(thread)
        db.commit()
        db.refresh(thread)
        thread_id = thread.id
        logger.info(f"✅ Created new thread: {thread_id}")
    
    message_text = request.message
    # --------------------------
    # 2. Get Chatbot Instance (BEFORE event_generator!)
    # --------------------------
    chatbot_agent = await get_chatbot_agent()
    
    # --------------------------
    # 3. Create SSE Event Generator
    # --------------------------
    async def event_generator():
        """Generate Server-Sent Events from chat stream."""
        try:
            # Stream chunks from agent
            async for chunk in chatbot_agent.chat_stream(
                message=message_text,
                user_id=user_id,
                thread_id=thread_id
            ):
                # Format as SSE
                event_data = json.dumps(chunk)
                yield f"data: {event_data}\n\n"
                logger.debug(f"📤 Sent chunk: {chunk.get('type', 'unknown')}")
            
            # Send completion signal
            yield "data: [DONE]\n\n"
            logger.info("✅ Stream completed, sent [DONE]")
            
        except Exception as e:
            logger.exception(f"❌ Stream generation failed")
            
            yield f"data: {e}\n\n"
        
        finally:
            # Update thread metadata after stream completes
            try:
                # Update thread title if needed
                if not thread.title or thread.title == "New conversation":
                    new_title = request.message[:50]
                    if len(request.message) > 50:
                        new_title += "..."
                    thread.title = new_title
                
                # Update timestamp
                thread.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"📝 Updated thread {thread_id} after stream")
            except Exception as e:
                logger.error(f"⚠️  Failed to update thread: {e}")
    
    # --------------------------
    # 4. Return Streaming Response
    # --------------------------
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


# --------------------------
# Keep original endpoint for backwards compatibility
# --------------------------


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Main chat endpoint with memory and RAG.
    
    Handles:
    - Automatic thread creation for new users
    - Thread validation for existing threads
    - Chat processing with memory
    """
    logger.info(
        f"💬 Chat request | user={current_user.id} | thread={request.thread_id}"
    )

    try:
        # --------------------------
        # Handle Thread Logic
        # --------------------------
        thread_id = request.thread_id
        
        if thread_id:
            # Thread ID provided - validate it exists and belongs to user
            thread = (
                db.query(Thread)
                .filter(
                    Thread.id == thread_id,
                    Thread.user_id == current_user.id,
                )
                .first()
            )
            
            if not thread:
                logger.info(f"Thread {thread_id} not found or does not belong to you")
                
                 
            
            logger.info(f"📝 Using existing thread: {thread_id}")
            
        else:
            # No thread ID provided - create a new thread
            logger.info("🆕 Creating new thread for user")
            
            thread = Thread(
                user_id=current_user.id,
                title=f"New conversation",  # You can update this later based on first message
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(thread)
            db.commit()
            db.refresh(thread)
            
            thread_id = thread.id
            logger.info(f"✅ Created new thread: {thread_id}")

        # --------------------------
        # Execute Chat with Agent
        # --------------------------
        # 2. Create async generator
        async def event_generator():
            # 3. Stream chunks from agent
            async for chunk in chatbot.chat_stream(...):
                # 4. Format as SSE
                yield f"data: {json.dumps(chunk)}\n\n"
            
            # 5. Send completion signal
            yield "data: [DONE]\n\n"
        
        # 6. Return streaming response
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream"
        )
        # --------------------------
        # Update Thread Title (Optional)
        # --------------------------
        # If this is the first message in a new thread, update the title
        if not thread.title or thread.title == "New conversation":
            # Generate a title from the first message (first 50 chars)
            new_title = request.message[:50] + "..." if len(request.message) > 50 else request.message
            thread.title = new_title
            thread.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"📝 Updated thread title: {new_title}")
        
        # Update thread timestamp
        thread.updated_at = datetime.utcnow()
        db.commit()

        logger.info(
            f"✅ Chat response | user={current_user.id} | "
            f"thread={thread_id} | response_length={len(result['response'])}"
        )

        return ChatResponse(
            message=result["response"],
            thread_id=thread_id,
            sources=result.get("sources"),
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(f"❌ Chat failed | user={current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat processing failed: {str(e)}"
        )




@router.get("/threads")
async def list_threads(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all threads for the current user.
    
    Returns threads ordered by most recently updated.
    """
    threads = (
        db.query(Thread)
        .filter(Thread.user_id == current_user.id)
        .order_by(Thread.updated_at.desc())
        .all()
    )
    
    logger.info(f"📋 Listed {len(threads)} threads for user {current_user.id}")
    
    return threads


@router.post("/threads/new")
async def create_thread(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Explicitly create a new thread.
    
    Useful for "New Chat" button in UI.
    """
    thread = Thread(
        user_id=current_user.id,
        title="New conversation",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(thread)
    db.commit()
    db.refresh(thread)
    
    logger.info(f"🆕 Created new thread {thread.id} for user {current_user.id}")
    
    return {
        "thread_id": thread.id,
        "message": "New thread created"
    }


@router.get("/threads/{thread_id}")
async def get_thread(
    thread_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a specific thread by ID.
    
    Validates ownership before returning.
    """
    thread = (
        db.query(Thread)
        .filter(
            Thread.id == thread_id,
            Thread.user_id == current_user.id,
        )
        .first()
    )
    
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found"
        )
    
    # Get history from checkpointer 
    chatbot = await get_chatbot_agent()
    history = await chatbot.get_thread_history(current_user.id, thread_id)
    logger.info(f'Retrieved {len(history)} messages for thread {thread_id}')
    logger.info(f"📋 Got thread {thread_id} for user {current_user.id}")
    
    return {'thread_id': thread_id, 'history': history} 


@router.delete("/threads/{thread_id}")
async def delete_thread(
    thread_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a thread.
    
    Note: This only deletes the Thread record in your app database.
    LangGraph's checkpointer data will remain (which is fine for memory).
    """
    thread = (
        db.query(Thread)
        .filter(
            Thread.id == thread_id,
            Thread.user_id == current_user.id,
        )
        .first()
    )
    
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found"
        )
    
    db.delete(thread)
    db.commit()
    
    logger.info(f"🗑️  Deleted thread {thread_id} for user {current_user.id}")
    
    return {"message": "Thread deleted successfully"}


@router.patch("/threads/{thread_id}")
async def update_thread_title(
    thread_id: int,
    title: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update thread title.
    
    Useful for renaming conversations.
    """
    thread = (
        db.query(Thread)
        .filter(
            Thread.id == thread_id,
            Thread.user_id == current_user.id,
        )
        .first()
    )
    
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found"
        )
    
    thread.title = title
    thread.updated_at = datetime.utcnow()
    db.commit()
    
    logger.info(f"✏️  Updated thread {thread_id} title to: {title}")
    
    return {"message": "Thread title updated", "title": title}