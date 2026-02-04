"""
🤖 Agentic RAG with Knowledge Base 
Clean Streamlit Implementation (No HTML/CSS)

Features:
✅ User Authentication
✅ Long Term Memory (Semantic Memory)
✅ Thread Management
✅ Document Upload & Management
✅ Real-time Streaming Chat
✅ Analytics Dashboard
✅ Debug Logging
"""

import streamlit as st
import requests
import json
import time
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import logging

# ========================================
# LOGGING CONFIGURATION
# ========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========================================
# CONFIGURATION
# ========================================
API_BASE_URL = "https://enterprise-ai-assistant-with-custom-knowledge-ba-production.up.railway.app/"

st.set_page_config(
    page_title="Agentic RAG with Knowledge Base",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
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
        "show_welcome": True,
        "stats_cache": None,
        "last_stats_update": None,
        "debug_logs": [],
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ========================================
# LOGGING HELPER
# ========================================
def log_debug(message: str):
    """Add debug log to session state and print to console"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    log_entry = f"[{timestamp}] {message}"
    logger.info(message)
    st.session_state.debug_logs.append(log_entry)
    if len(st.session_state.debug_logs) > 100:
        st.session_state.debug_logs = st.session_state.debug_logs[-100:]

# ========================================
# API HELPER FUNCTIONS
# ========================================

def get_headers() -> Dict[str, str]:
    """Get authorization headers"""
    if st.session_state.token:
        return {"Authorization": f"Bearer {st.session_state.token}"}
    return {}

def api_call(method: str, endpoint: str, **kwargs) -> Tuple[bool, any]:
    """Generic API call function with error handling"""
    try:
        url = f"{API_BASE_URL}{endpoint}"
        log_debug(f"API {method} {endpoint}")
        
        response = requests.request(method, url, timeout=30, **kwargs)
        log_debug(f"Response: {response.status_code}")
        
        if response.status_code in [200, 201]:
            try:
                return True, response.json()
            except:
                return True, response.text
        else:
            try:
                error_msg = response.json().get("detail", f"Error {response.status_code}")
            except:
                error_msg = f"Error {response.status_code}"
            log_debug(f"API Error: {error_msg}")
            return False, error_msg
            
    except requests.exceptions.Timeout:
        log_debug("⏱️ Request timeout")
        return False, "Request timeout. Please try again."
    except requests.exceptions.ConnectionError:
        log_debug("🔌 Connection error")
        return False, "Connection error. Please check your internet connection."
    except Exception as e:
        log_debug(f"💥 Exception: {str(e)}")
        return False, f"Unexpected error: {str(e)}"

# ========================================
# AUTHENTICATION FUNCTIONS
# ========================================

def register_user(username: str, email: str, password: str) -> Tuple[bool, str]:
    """Register a new user"""
    return api_call(
        "POST",
        "/api/auth/register",
        json={"username": username, "email": email, "password": password}
    )

def login_user(username: str, password: str) -> Tuple[bool, str]:
    """Login user and store token"""
    success, data = api_call(
        "POST",
        "/api/auth/login",
        data={"username": username, "password": password}
    )
    
    if success:
        st.session_state.token = data["access_token"]
        st.session_state.username = username
        log_debug(f"✅ User logged in: {username}")
        return True, "Login successful!"
    
    return False, data

def logout():
    """Clear session and logout"""
    log_debug("🚪 User logged out")
    keys_to_clear = ["token", "username", "current_thread_id", "messages", 
                     "threads", "documents", "stats_cache", "last_stats_update"]
    for key in keys_to_clear:
        if key in ["token", "username", "current_thread_id", "stats_cache", "last_stats_update"]:
            st.session_state[key] = None
        else:
            st.session_state[key] = []
    st.session_state.show_welcome = True

# ========================================
# THREAD MANAGEMENT FUNCTIONS
# ========================================

def get_threads(force_refresh: bool = False) -> List[Dict]:
    """Fetch all threads"""
    # Use cached threads if available and not forcing refresh
    if not force_refresh and st.session_state.threads:
        return st.session_state.threads
    
    success, data = api_call("GET", "/api/chat/threads", headers=get_headers())
    if success:
        st.session_state.threads = data
        log_debug(f"📚 Loaded {len(data)} threads")
        return data
    return []

def create_thread() -> Optional[str]:
    """Create a new thread"""
    success, data = api_call("POST", "/api/chat/threads/new", headers=get_headers())
    if success:
        log_debug(f"➕ Created thread: {data['thread_id']}")
        return data["thread_id"]
    return None

def get_thread_history(thread_id: str) -> List[Dict]:
    """Get thread history"""
    log_debug(f"📖 Loading history for: {thread_id}")
    success, data = api_call(
        "GET",
        f"/api/chat/threads/{thread_id}",
        headers=get_headers()
    )
    if success:
        history = data.get("history", [])
        log_debug(f"✅ Loaded {len(history)} messages")
        return history
    return []

def delete_thread(thread_id: str) -> bool:
    """Delete a thread"""
    success, _ = api_call(
        "DELETE",
        f"/api/chat/threads/{thread_id}",
        headers=get_headers()
    )
    if success:
        log_debug(f"🗑️ Deleted thread: {thread_id}")
    return success

def update_thread_title(thread_id: str, new_title: str) -> bool:
    """Update thread title"""
    success, _ = api_call(
        "PATCH",
        f"/api/chat/threads/{thread_id}",
        headers=get_headers(),
        params={"title": new_title}  # ← Fix: Send as query parameter to match backend
    )
    if success:
        log_debug(f"✏️ Updated title: {new_title}")
        # Force refresh threads list
        get_threads(force_refresh=True)
    return success

# ========================================
# CHAT FUNCTIONS (STREAMING)
# ========================================

def stream_message(message: str, thread_id: Optional[str] = None):
    """Stream chat response with detailed logging"""
    try:
        log_debug(f"🚀 Stream START - Msg: '{message[:40]}...'")
        log_debug(f"🔖 Thread: {thread_id}")
        
        response = requests.post(
            f"{API_BASE_URL}/api/chat/stream",
            headers=get_headers(),
            json={"message": message, "thread_id": thread_id},
            stream=True,
            timeout=120
        )
        
        log_debug(f"📡 HTTP {response.status_code}")
        
        if response.status_code != 200:
            error_msg = f"Error: {response.status_code}"
            log_debug(f"❌ {error_msg}")
            yield {"type": "error", "message": error_msg}
            return
        
        chunk_count = 0
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            
            data_str = line[6:]
            
            if data_str == "[DONE]":
                log_debug(f"✅ Stream DONE - {chunk_count} chunks")
                break
            
            try:
                chunk = json.loads(data_str)
                chunk_count += 1
                chunk_type = chunk.get("type")
                
                if chunk_type == "content":
                    content_len = len(chunk.get("data", ""))
                    log_debug(f"💬 Content #{chunk_count} ({content_len} chars)")
                elif chunk_type == "status":
                    log_debug(f"📊 Status: {chunk.get('status')}")
                elif chunk_type == "tool_start":
                    log_debug(f"🔧 Tool: {chunk.get('tool')}")
                elif chunk_type == "sources":
                    log_debug(f"📚 Sources: {len(chunk.get('sources', []))}")
                elif chunk_type == "error":
                    log_debug(f"❌ Error: {chunk.get('message')}")
                
                yield chunk
                
            except json.JSONDecodeError as e:
                log_debug(f"⚠️ JSON error: {str(e)}")
                continue
                
    except requests.exceptions.Timeout:
        log_debug("⏱️ Stream timeout")
        yield {"type": "error", "message": "Request timeout. Please try again."}
    except Exception as e:
        log_debug(f"💥 Stream error: {str(e)}")
        yield {"type": "error", "message": str(e)}

# ========================================
# DOCUMENT FUNCTIONS
# ========================================

def upload_document(file) -> Tuple[bool, str]:
    """Upload a PDF document"""
    log_debug(f"📤 Uploading: {file.name}")
    files = {"file": (file.name, file.getvalue(), "application/pdf")}
    return api_call(
        "POST",
        "/api/documents/upload",
        headers=get_headers(),
        files=files
    )

def get_documents() -> List[Dict]:
    """Get all documents"""
    success, data = api_call("GET", "/api/documents/", headers=get_headers())
    if success:
        st.session_state.documents = data
        log_debug(f"📄 Loaded {len(data)} documents")
        return data
    return []

def delete_document(doc_id: str) -> bool:
    """Delete a document"""
    success, _ = api_call(
        "DELETE",
        f"/api/documents/{doc_id}",
        headers=get_headers()
    )
    if success:
        log_debug(f"🗑️ Deleted document: {doc_id}")
    return success

def get_upload_stats() -> Optional[Dict]:
    """Get document upload statistics with caching"""
    current_time = time.time()
    
    if (st.session_state.last_stats_update and 
        current_time - st.session_state.last_stats_update < 30 and
        st.session_state.stats_cache):
        return st.session_state.stats_cache
    
    success, data = api_call(
        "GET",
        "/api/documents/stats/summary",
        headers=get_headers()
    )
    
    if success:
        st.session_state.stats_cache = data
        st.session_state.last_stats_update = current_time
        return data
    return None

# ========================================
# UI COMPONENTS
# ========================================

def render_login_page():
    """Render login/register page"""
    
    st.title("🤖 Agentic RAG Assistant")
    st.subheader("Experience AI-powered conversations with advanced RAG technology")
    
    # Feature highlights
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("🧠 **Smart Memory**\n\nLong-term semantic memory for context-aware conversations")
    
    with col2:
        st.info("📚 **Document RAG**\n\nUpload and chat with your PDF documents seamlessly")
    
    with col3:
        st.info("⚡ **Real-time AI**\n\nStreaming responses with multi-tool integration")
    
    st.divider()
    
    # Login/Register Tabs
    tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
    
    # LOGIN TAB
    with tab1:
        st.subheader("Welcome Back!")
        
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            
            col1, col2 = st.columns([3, 1])
            with col1:
                submit = st.form_submit_button("🚀 Sign In", use_container_width=True)
            
            if submit:
                if username and password:
                    with st.spinner("🔐 Authenticating..."):
                        success, message = login_user(username, password)
                        if success:
                            st.success("✅ " + message)
                            st.balloons()
                            time.sleep(0.8)
                            st.rerun()
                        else:
                            st.error("❌ " + message)
                else:
                    st.warning("⚠️ Please fill in all fields")
    
    # REGISTER TAB
    with tab2:
        st.subheader("Create Your Account")
        
        with st.form("register_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                reg_username = st.text_input("Username", placeholder="Choose a username")
            
            with col2:
                reg_email = st.text_input("Email", placeholder="your.email@example.com")
            
            reg_password = st.text_input("Password", type="password", placeholder="Create a password")
            reg_password2 = st.text_input("Confirm Password", type="password", placeholder="Confirm password")
            
            agree_terms = st.checkbox("I agree to the Terms of Service and Privacy Policy")
            
            submit_reg = st.form_submit_button("📝 Create Account", use_container_width=True)
            
            if submit_reg:
                if not agree_terms:
                    st.error("❌ Please agree to the terms and conditions")
                elif reg_username and reg_email and reg_password:
                    if reg_password == reg_password2:
                        if len(reg_password) < 8:
                            st.error("❌ Password must be at least 8 characters long")
                        else:
                            with st.spinner("📝 Creating your account..."):
                                success, message = register_user(reg_username, reg_email, reg_password)
                                if success:
                                    st.success("✅ Account created successfully! Please login.")
                                    st.balloons()
                                else:
                                    st.error("❌ " + str(message))
                    else:
                        st.error("❌ Passwords don't match")
                else:
                    st.warning("⚠️ Please fill in all fields")

def render_sidebar():
    """Render sidebar with user profile and navigation"""
    
    with st.sidebar:
        # User Profile
        st.header(f"👤 {st.session_state.username}")
        st.caption("AI Power User")
        
        if st.button("🚪 Logout", use_container_width=True):
            logout()
            st.rerun()
        
        st.divider()
        
        # Conversations Section
        st.subheader("💬 Conversations")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("➕ New Chat", use_container_width=True):
                with st.spinner("Creating new conversation..."):
                    new_thread_id = create_thread()
                    if new_thread_id:
                        st.session_state.current_thread_id = new_thread_id
                        st.session_state.messages = []
                        st.success("✅ New chat created!")
                        time.sleep(0.5)
                        st.rerun()
        
        with col2:
            if st.button("🔄", use_container_width=True, help="Refresh"):
                get_threads(force_refresh=True)
                st.rerun()
        
        # Thread List
        threads = get_threads(force_refresh=False)  # Use cached data by default
        
        if threads:
            st.caption(f"**{len(threads)} active conversations**")
            
            for thread in threads:
                title = thread.get('title', 'Untitled')
                if len(title) > 28:
                    title = title[:28] + "..."
                
                is_current = thread['id'] == st.session_state.current_thread_id
                
                col1, col2 = st.columns([5, 1])
                
                with col1:
                    emoji = "📌" if is_current else "💬"
                    
                    if st.button(f"{emoji} {title}", key=f"thread_{thread['id']}", use_container_width=True):
                        if not is_current:
                            st.session_state.current_thread_id = thread['id']
                            st.session_state.messages = get_thread_history(thread['id'])
                            st.rerun()
                
                with col2:
                    if st.button("🗑️", key=f"delete_{thread['id']}", help="Delete"):
                        if delete_thread(thread['id']):
                            if thread['id'] == st.session_state.current_thread_id:
                                st.session_state.current_thread_id = None
                                st.session_state.messages = []
                            st.success("✅ Deleted!")
                            time.sleep(0.5)
                            st.rerun()
        else:
            st.info("💡 No conversations yet. Start a new one!")
        
        st.divider()
        
        # Rename Current Thread
        if st.session_state.current_thread_id:
            with st.expander("✏️ Rename Current Chat"):
                # Get current thread title
                current_thread = next(
                    (t for t in st.session_state.threads if t['id'] == st.session_state.current_thread_id),
                    None
                )
                current_title = current_thread['title'] if current_thread else ""
                
                new_title = st.text_input(
                    "New title", 
                    value=current_title,  # ← Show current title
                    placeholder="Enter a title"
                )
                if st.button("💾 Save Title", use_container_width=True):
                    if new_title and new_title != current_title:
                        with st.spinner("Updating title..."):
                            if update_thread_title(st.session_state.current_thread_id, new_title):
                                st.success("✅ Title updated!")
                                time.sleep(0.3)
                                st.rerun()
                            else:
                                st.error("❌ Failed to update title")
                    elif new_title == current_title:
                        st.info("💡 Title unchanged")
                    else:
                        st.warning("⚠️ Please enter a title")
        
        st.divider()
        
        # Knowledge Base Section
        st.subheader("📚 Knowledge Base")
        
        uploaded_file = st.file_uploader("Upload PDF Document", type=["pdf"])
        
        if uploaded_file:
            if st.button("📤 Upload Document", use_container_width=True):
                with st.spinner("📤 Uploading..."):
                    success, message = upload_document(uploaded_file)
                    if success:
                        st.success("✅ Document uploaded!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
        
        # Document List
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
                
                with st.expander(f"{status_emoji} {doc['filename'][:25]}..."):
                    st.write(f"**Status:** {doc['status'].upper()}")
                    st.write(f"**Size:** {doc['file_size']:,} bytes")
                    st.write(f"**Uploaded:** {doc['uploaded_at'][:16]}")
                    
                    if doc.get('error_message'):
                        st.error(f"⚠️ {doc['error_message']}")
                    
                    if st.button("🗑️ Remove", key=f"del_doc_{doc['id']}", use_container_width=True):
                        if delete_document(doc['id']):
                            st.success("✅ Removed!")
                            time.sleep(0.5)
                            st.rerun()
        else:
            st.info("💡 No documents yet")
        
        st.divider()
        
        # Statistics
        with st.expander("📊 Statistics"):
            stats = get_upload_stats()
            if stats:
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total", stats.get('total_uploads', 0))
                    st.metric("Processing", stats.get('processing', 0))
                
                with col2:
                    st.metric("Ready", stats.get('completed', 0))
                    st.metric("Failed", stats.get('failed', 0))

def render_chat_interface():
    """Render main chat interface"""
    
    st.title("💬 Agentic RAG with Knowledge Base")
    
    if st.session_state.current_thread_id:
        st.info(f"🔖 Active Thread: `{st.session_state.current_thread_id}`")
    else:
        st.info("👋 Start a new conversation or select one from the sidebar!")
    
    # Debug logs
    with st.expander("🐛 Debug Logs"):
        if st.session_state.debug_logs:
            col1, col2 = st.columns([4, 1])
            with col2:
                if st.button("🗑️ Clear"):
                    st.session_state.debug_logs = []
                    st.rerun()
            
            log_text = "\n".join(st.session_state.debug_logs[-50:])
            st.code(log_text, language="log")
        else:
            st.info("No logs yet")
    
    st.divider()
    
    # Display messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
            if msg.get("sources"):
                with st.expander("📚 Sources"):
                    for idx, source in enumerate(msg["sources"], 1):
                        st.markdown(f"**{idx}.** {source}")
    
    # Chat input
    user_input = st.chat_input("💭 Ask me anything...")
    
    if user_input:
        # Add user message
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })
        
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Get AI response
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            sources = []
            
            current_tool_status = None
            current_tool_name = None
            
            for chunk in stream_message(user_input, st.session_state.current_thread_id):
                chunk_type = chunk.get("type")
                
                if chunk_type == "status":
                    status = chunk.get("status")
                    message = chunk.get("message", "Processing...")
                    
                    if status == "retrieving":
                        with st.status("🧠 Retrieving Memory", state="running") as mem_status:
                            st.write(message)
                            mem_status.update(label="🧠 Memory Retrieved", state="complete")
                
                elif chunk_type == "tool_start":
                    tool_name = chunk.get("tool", "unknown")
                    current_tool_name = tool_name
                    
                    tool_configs = {
                        "search_my_documents": ("🔍", "Searching Documents"),
                        "calculator": ("🧮", "Calculator"),
                        "google_web_search": ("🌐", "Web Search"),
                        "web_scrape": ("📄", "Web Scraper")
                    }
                    
                    icon, label = tool_configs.get(tool_name, ("🔧", tool_name.replace("_", " ").title()))
                    
                    current_tool_status = st.status(f"{icon} {label}", expanded=True, state="running")
                    
                    with current_tool_status:
                        st.write(f"Executing {tool_name}...")
                
                elif chunk_type == "tool_complete":
                    tool_name = chunk.get("tool", current_tool_name or "unknown")
                    
                    if current_tool_status:
                        tool_configs = {
                            "search_my_documents": "🔍",
                            "calculator": "🧮",
                            "google_web_search": "🌐",
                            "web_scrape": "📄"
                        }
                        icon = tool_configs.get(tool_name, "🔧")
                        
                        current_tool_status.update(
                            label=f"✅ {icon} {tool_name.replace('_', ' ').title()} - Complete",
                            state="complete",
                            expanded=False
                        )
                        current_tool_status = None
                
                elif chunk_type == "content":
                    full_response += chunk.get("data", "")
                    message_placeholder.markdown(full_response + "▌")
                
                elif chunk_type == "sources":
                    sources = chunk.get("sources", [])
                
                elif chunk_type == "error":
                    error_msg = chunk.get('message', 'Unknown error')
                    
                    if current_tool_status:
                        current_tool_status.update(
                            label=f"❌ Error",
                            state="error"
                        )
                        with current_tool_status:
                            st.error(error_msg)
                    else:
                        st.error(f"❌ {error_msg}")
                    break
            
            message_placeholder.markdown(full_response)
            
            if sources:
                with st.expander("📚 Sources"):
                    for idx, source in enumerate(sources, 1):
                        st.markdown(f"**{idx}.** {source}")
        
        # Save to history
        st.session_state.messages.append({
            "role": "assistant",
            "content": full_response,
            "sources": sources
        })
        
        st.rerun()

# ========================================
# MAIN APP
# ========================================

def main():
    """Main application"""
    
    log_debug("🎬 App started")
    
    if not st.session_state.token:
        render_login_page()
    else:
        if st.session_state.current_thread_id and not st.session_state.messages:
            st.session_state.messages = get_thread_history(st.session_state.current_thread_id)
        
        render_sidebar()
        render_chat_interface()
    
    # Footer
    st.divider()
    st.caption("Built with ❤️ using Streamlit | Powered by LangGraph & FastAPI")

if __name__ == "__main__":
    main()