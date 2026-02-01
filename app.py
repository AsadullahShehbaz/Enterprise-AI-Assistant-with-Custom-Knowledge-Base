"""
🤖 Persistent Chatbot - Clean Streamlit UI
A beginner-friendly interface for AI chatbot with memory and RAG.

Features:
✅ User Authentication (Login/Register)
✅ Thread Management (Create, Switch, Delete, Update Title)
✅ Document Upload & Management
✅ Real-time Streaming Chat
✅ Document Statistics
"""

import streamlit as st
import requests
import json
import time
from datetime import datetime

# ========================================
# CONFIGURATION
# ========================================
API_BASE_URL = "http://localhost:8010"

st.set_page_config(
    page_title="AI Chatbot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========================================
# SESSION STATE INITIALIZATION
# ========================================
def init_session_state():
    """Initialize all session state variables"""
    defaults = {
        "token": None,
        "username": None,
        "current_thread_id": None,
        "messages": [],
        "threads": [],
        "documents": [],
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ========================================
# API HELPER FUNCTIONS
# ========================================

def get_headers():
    """Get authorization headers"""
    if st.session_state.token:
        return {"Authorization": f"Bearer {st.session_state.token}"}
    return {}

def api_call(method, endpoint, **kwargs):
    """
    Generic API call function
    
    Args:
        method: HTTP method (GET, POST, DELETE, PATCH)
        endpoint: API endpoint path
        **kwargs: Additional arguments for requests
    
    Returns:
        tuple: (success: bool, data: dict/list/str)
    """
    try:
        url = f"{API_BASE_URL}{endpoint}"
        response = requests.request(method, url, **kwargs)
        
        if response.status_code in [200, 201]:
            try:
                return True, response.json()
            except:
                return True, response.text
        else:
            error_msg = response.json().get("detail", f"Error {response.status_code}")
            return False, error_msg
            
    except Exception as e:
        return False, str(e)

# ========================================
# AUTHENTICATION FUNCTIONS
# ========================================

def register_user(username, email, password):
    """Register a new user"""
    return api_call(
        "POST",
        "/api/auth/register",
        json={"username": username, "email": email, "password": password}
    )

def login_user(username, password):
    """Login user and store token"""
    success, data = api_call(
        "POST",
        "/api/auth/login",
        data={"username": username, "password": password}
    )
    
    if success:
        st.session_state.token = data["access_token"]
        st.session_state.username = username
        return True, "Login successful!"
    
    return False, data

def logout():
    """Clear session and logout"""
    for key in ["token", "username", "current_thread_id", "messages", "threads", "documents"]:
        st.session_state[key] = None if key in ["token", "username", "current_thread_id"] else []

# ========================================
# THREAD MANAGEMENT FUNCTIONS
# ========================================

def get_threads():
    """Fetch all threads"""
    success, data = api_call("GET", "/api/chat/threads", headers=get_headers())
    if success:
        st.session_state.threads = data
        return data
    return []

def create_thread():
    """Create a new thread"""
    success, data = api_call("POST", "/api/chat/threads/new", headers=get_headers())
    if success:
        return data["thread_id"]
    return None

def get_thread_history(thread_id):
    """Get thread history"""
    success, data = api_call(
        "GET",
        f"/api/chat/threads/{thread_id}",
        headers=get_headers()
    )
    if success:
        return data.get("history", [])
    return []

def delete_thread(thread_id):
    """Delete a thread"""
    success, _ = api_call(
        "DELETE",
        f"/api/chat/threads/{thread_id}",
        headers=get_headers()
    )
    return success

def update_thread_title(thread_id, new_title):
    """Update thread title"""
    success, _ = api_call(
        "PATCH",
        f"/api/chat/threads/{thread_id}",
        headers=get_headers(),
        json={"title": new_title}
    )
    return success

# ========================================
# CHAT FUNCTIONS
# ========================================

def stream_message(message, thread_id=None):
    """
    Stream chat response
    
    Yields:
        dict: Chunk with type and data
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/chat/stream",
            headers=get_headers(),
            json={"message": message, "thread_id": thread_id},
            stream=True
        )
        
        if response.status_code != 200:
            yield {"type": "error", "message": f"Error: {response.status_code}"}
            return
        
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            
            data_str = line[6:]
            
            if data_str == "[DONE]":
                break
            
            try:
                chunk = json.loads(data_str)
                yield chunk
            except json.JSONDecodeError:
                continue
                
    except Exception as e:
        yield {"type": "error", "message": str(e)}

# ========================================
# DOCUMENT FUNCTIONS
# ========================================

def upload_document(file):
    """Upload a PDF document"""
    files = {"file": (file.name, file.getvalue(), "application/pdf")}
    return api_call(
        "POST",
        "/api/documents/upload",
        headers=get_headers(),
        files=files
    )

def get_documents():
    """Get all documents"""
    success, data = api_call("GET", "/api/documents/", headers=get_headers())
    if success:
        st.session_state.documents = data
        return data
    return []

def delete_document(doc_id):
    """Delete a document"""
    success, _ = api_call(
        "DELETE",
        f"/api/documents/{doc_id}",
        headers=get_headers()
    )
    return success

def get_upload_stats():
    """Get document upload statistics"""
    success, data = api_call(
        "GET",
        "/api/documents/stats/summary",
        headers=get_headers()
    )
    if success:
        return data
    return None

# ========================================
# UI COMPONENTS
# ========================================

def render_login_page():
    """Render login/register page"""
    
    st.title("🤖 AI Chatbot with Memory")
    st.subheader("Your intelligent assistant")
    
    tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
    
    # LOGIN TAB
    with tab1:
        st.subheader("Login to your account")
        
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submit = st.form_submit_button("🚀 Login", use_container_width=True, type="primary")
            
            if submit:
                if username and password:
                    with st.spinner("Logging in..."):
                        success, message = login_user(username, password)
                        if success:
                            st.success("✅ " + message)
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error("❌ " + message)
                else:
                    st.warning("⚠️ Please fill in all fields")
    
    # REGISTER TAB
    with tab2:
        st.subheader("Create a new account")
        
        with st.form("register_form"):
            reg_username = st.text_input("Username", placeholder="Choose a username")
            reg_email = st.text_input("Email", placeholder="your.email@example.com")
            reg_password = st.text_input("Password", type="password", placeholder="Create a password")
            reg_password2 = st.text_input("Confirm Password", type="password", placeholder="Confirm your password")
            submit_reg = st.form_submit_button("📝 Create Account", use_container_width=True, type="primary")
            
            if submit_reg:
                if reg_username and reg_email and reg_password:
                    if reg_password == reg_password2:
                        with st.spinner("Creating account..."):
                            success, message = register_user(reg_username, reg_email, reg_password)
                            if success:
                                st.success("✅ Account created! Please login.")
                            else:
                                st.error("❌ " + message)
                    else:
                        st.error("❌ Passwords don't match")
                else:
                    st.warning("⚠️ Please fill in all fields")

def render_sidebar():
    """Render sidebar with user info, threads, and documents"""
    
    with st.sidebar:
        # User Info
        st.header(f"👤 {st.session_state.username}")
        
        if st.button("🚪 Logout", use_container_width=True):
            logout()
            st.rerun()
        
        st.divider()
        
        # NEW CHAT SECTION
        st.subheader("💬 Conversations")
        
        if st.button("➕ New Chat", use_container_width=True, type="primary"):
            with st.spinner("Creating new chat..."):
                new_thread_id = create_thread()
                if new_thread_id:
                    st.session_state.current_thread_id = new_thread_id
                    st.session_state.messages = []
                    st.success("✅ New chat created!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("❌ Failed to create chat")
        
        # THREAD LIST
        threads = get_threads()
        
        if threads:
            st.caption(f"**{len(threads)} conversations**")
            
            for thread in threads:
                title = thread.get('title', 'Untitled')
                if len(title) > 35:
                    title = title[:35] + "..."
                
                is_current = thread['id'] == st.session_state.current_thread_id
                
                # Create columns for thread button and delete
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    if st.button(
                        f"{'📌' if is_current else '💬'} {title}",
                        key=f"thread_{thread['id']}",
                        use_container_width=True,
                        type="primary" if is_current else "secondary"
                    ):
                        if not is_current:
                            st.session_state.current_thread_id = thread['id']
                            st.session_state.messages = get_thread_history(thread['id'])
                            st.rerun()
                
                with col2:
                    if st.button("🗑️", key=f"delete_{thread['id']}", help="Delete this chat"):
                        if delete_thread(thread['id']):
                            if thread['id'] == st.session_state.current_thread_id:
                                st.session_state.current_thread_id = None
                                st.session_state.messages = []
                            st.success("✅ Deleted!")
                            time.sleep(0.5)
                            st.rerun()
        else:
            st.info("💡 No chats yet. Start a new one!")
        
        st.divider()
        
        # RENAME CURRENT THREAD
        if st.session_state.current_thread_id:
            with st.expander("✏️ Rename Current Chat"):
                new_title = st.text_input("New title", key="rename_input")
                if st.button("💾 Save Title", use_container_width=True):
                    if new_title:
                        if update_thread_title(st.session_state.current_thread_id, new_title):
                            st.success("✅ Title updated!")
                            time.sleep(0.5)
                            st.rerun()
                    else:
                        st.warning("⚠️ Enter a title")
        
        st.divider()
        
        # DOCUMENT UPLOAD SECTION
        st.subheader("📄 Documents")
        
        uploaded_file = st.file_uploader(
            "Upload PDF for RAG",
            type=["pdf"],
            help="Upload PDF documents to chat about them"
        )
        
        if uploaded_file:
            if st.button("📤 Upload Document", use_container_width=True, type="primary"):
                with st.spinner("Uploading..."):
                    success, message = upload_document(uploaded_file)
                    if success:
                        st.success("✅ Document uploaded!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
        
        # DOCUMENT LIST
        st.caption("**Your Documents:**")
        
        documents = get_documents()
        
        if documents:
            for doc in documents:
                status_emoji = {
                    "pending": "⏳",
                    "processing": "⚙️",
                    "completed": "✅",
                    "failed": "❌"
                }.get(doc['status'], "❓")
                
                with st.expander(f"{status_emoji} {doc['filename'][:30]}..."):
                    st.write(f"**Status:** {doc['status'].upper()}")
                    st.write(f"**Size:** {doc['file_size']:,} bytes")
                    st.write(f"**Uploaded:** {doc['uploaded_at'][:16]}")
                    
                    if doc.get('error_message'):
                        st.error(f"Error: {doc['error_message']}")
                    
                    if st.button("🗑️ Delete", key=f"del_doc_{doc['id']}", use_container_width=True):
                        if delete_document(doc['id']):
                            st.success("✅ Deleted!")
                            time.sleep(0.5)
                            st.rerun()
        else:
            st.info("💡 No documents uploaded yet")
        
        # UPLOAD STATISTICS
        st.divider()
        
        stats = get_upload_stats()
        if stats:
            st.subheader("📊 Statistics")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Uploads", stats.get('total_uploads', 0))
            with col2:
                st.metric("Completed", stats.get('completed', 0))
            
            col3, col4 = st.columns(2)
            with col3:
                st.metric("Processing", stats.get('processing', 0))
            with col4:
                st.metric("Failed", stats.get('failed', 0))

def render_chat_interface():
    """Render main chat interface"""
    
    # Header
    st.title("💬 AI Assistant")
    st.caption("Powered by LangGraph & RAG")
    
    # Thread info
    if st.session_state.current_thread_id:
        st.info(f"🔖 Thread ID: {st.session_state.current_thread_id}")
    else:
        st.warning("👋 Start a new conversation or select one from the sidebar")
    
    st.divider()
    
    # Display message history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            
            # Show sources if available
            if msg.get("sources"):
                with st.expander("📚 Sources Used"):
                    for source in msg["sources"]:
                        st.caption(f"• {source}")
    
    # Chat input
    user_input = st.chat_input("💭 Type your message here...")
    
    if user_input:
        # Add user message
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })
        
        # Display user message
        with st.chat_message("user"):
            st.write(user_input)
        
        # Get and display AI response
        with st.chat_message("assistant"):
            status_placeholder = st.empty()
            message_placeholder = st.empty()
            full_response = ""
            is_generating = False
            
            # Stream the response
            for chunk in stream_message(user_input, st.session_state.current_thread_id):
                chunk_type = chunk.get("type")
                
                # Handle different chunk types
                if chunk_type == "status":
                    status = chunk.get("status")
                    message = chunk.get("message", "Processing...")
                    
                    if status == "retrieving":
                        status_placeholder.info(f"🔍 {message}")
                    elif status == "complete":
                        status_placeholder.success(f"✅ {message}")
                        time.sleep(1)
                        status_placeholder.empty()
                    elif status == "started":
                        status_placeholder.info(f"⚡ {message}")
                        time.sleep(1)
                        status_placeholder.empty()
                
                elif chunk_type == "tool_start":
                    tool_name = chunk.get("tool", "unknown")
                    
                    tool_display = {
                        "search_my_documents": "🔍 Searching your documents",
                        "calculator": "🧮 Calculating",
                        "google_web_search": "🌐 Searching the web",
                        "web_scrape": "📄 Fetching webpage"
                    }
                    
                    display_name = tool_display.get(tool_name, f"🔧 {tool_name}")
                    status_placeholder.info(display_name + "...")
                
                elif chunk_type == "tool_complete":
                    message = chunk.get("message", "Tool complete")
                    status_placeholder.success(f"✅ {message}")
                    time.sleep(1)
                    status_placeholder.empty()
                
                elif chunk_type == "content":
                    if not is_generating:
                        status_placeholder.empty()
                        is_generating = True
                    
                    full_response += chunk.get("data", "")
                    message_placeholder.markdown(full_response + "▌")
                
                elif chunk_type == "error":
                    status_placeholder.error(f"❌ {chunk.get('message')}")
                    break
            
            # Clear status and show final response
            status_placeholder.empty()
            message_placeholder.markdown(full_response)
        
        # Add assistant message to history
        st.session_state.messages.append({
            "role": "assistant",
            "content": full_response
        })
        
        # Auto-refresh to update thread list
        st.rerun()

# ========================================
# MAIN APP
# ========================================

def main():
    """Main application logic"""
    
    # Check if user is logged in
    if not st.session_state.token:
        render_login_page()
    else:
        # Auto-load thread history if needed
        if st.session_state.current_thread_id and not st.session_state.messages:
            st.session_state.messages = get_thread_history(st.session_state.current_thread_id)
        
        # Render sidebar and chat
        render_sidebar()
        render_chat_interface()
    
    # Footer
    st.divider()
    st.caption("Built with ❤️ using Streamlit | Powered by LangGraph & FastAPI")

# ========================================
# RUN APP
# ========================================

if __name__ == "__main__":
    main()