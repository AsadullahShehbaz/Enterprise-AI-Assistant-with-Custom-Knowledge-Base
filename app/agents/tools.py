# app/agents/tools.py - FIXED VERSION WITH PROPER ERROR HANDLING

from langchain_community.document_loaders import WebBaseLoader
from langchain_google_community import GoogleSearchAPIWrapper
from app.context.user_context import get_current_user_id  
from langchain.tools import tool
from app.rag.vector_store import get_pdf_processor
from app.config import get_settings
from app.logg import logger
import math
import traceback

settings = get_settings()

# Google search setup
try:
    google_search = GoogleSearchAPIWrapper(
        google_api_key=settings.GOOGLE_API_KEY,
        google_cse_id=settings.GOOGLE_CSE_ID
    )
except:
    google_search = None


@tool(parse_docstring=False)
def calculator(expression: str) -> str:
    """
    Evaluates mathematical expressions.
    Supports: +, -, *, /, **, sqrt, sin, cos, tan, log, ln, pi, e
    Example: "sqrt(16) + 2**3" returns "Result: 12"
    """
    try:
        expression = expression.strip()
        expression = expression.replace("sqrt", "math.sqrt")
        expression = expression.replace("sin", "math.sin")
        expression = expression.replace("cos", "math.cos")
        expression = expression.replace("tan", "math.tan")
        expression = expression.replace("log", "math.log10")
        expression = expression.replace("ln", "math.log")
        expression = expression.replace("pi", "math.pi")
        expression = expression.replace("e", "math.e")
        
        safe_dict = {
            "math": math,
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "__builtins__": {}
        }
        
        result = eval(expression, safe_dict)
        
        if isinstance(result, float):
            if result.is_integer():
                result = int(result)
            else:
                result = round(result, 10)
        
        logger.info(f"🧮 Calculator: {expression} = {result}")
        return f"Result: {result}"
        
    except Exception as e:
        logger.error(f"❌ Calculator error: {e}")
        return f"Error: {str(e)}"


@tool(parse_docstring=False)
def search_my_documents(query: str) -> str:
    """Search uploaded PDF documents for information. Use when user  mentions 'my document', 'my PDF', 'my file', or uploaded content etc  """
    # CRITICAL: Add extensive logging at the very start
    
    logger.info("=" * 80)
    logger.info("🔍 RAG TOOL INVOKED")
    logger.info(f"   Query: {query}")
    # Get user_id from context (set in chatbot.py before graph invocation)
    user_id = get_current_user_id()
    logger.info(f"🔍 RAG tool called - user_id={user_id}, query={query}")
    logger.info("=" * 80)
    
    try:
        # Get PDF processor
        logger.info("📚 Getting PDF processor...")
        pdf_processor = get_pdf_processor()
        logger.info("✅ PDF processor retrieved")
        
        # Check if user has FAISS index
        logger.info(f"🔎 Checking for vector store for user {user_id}...")
        vectorstore = pdf_processor.get_vectorstore(user_id)
        
        if vectorstore is None:
            logger.warning(f"📭 No vector store found for user {user_id}")
            return (
                "I don't see any uploaded documents in your account yet.\n\n"
                "To use this feature:\n"
                "1. Upload a PDF document using the upload button\n"
                "2. Wait for processing to complete\n"
                "3. Ask me questions about your document"
            )
        
        logger.info(f"✅ Vector store loaded for user {user_id}")
        
        # Query documents
        logger.info(f"🔎 Searching vector store with query: '{query}'")
        results = pdf_processor.query_documents(user_id, query, k=4)
        
        if not results:
            logger.warning("📭 No matching documents found in vector store")
            return (
                "I couldn't find any relevant information in your documents for this query.\n"
                "Try rephrasing your question or check if the information is in your uploaded files."
            )
        
        logger.info(f"✅ Found {len(results)} relevant chunks")
        
        # Format response
        response_lines = [
            f"I found {len(results)} relevant sections in your documents:\n"
        ]
        
        for i, doc in enumerate(results, 1):
            source = doc['metadata'].get('source', 'Unknown')
            page = doc['metadata'].get('page', '?')
            content = doc['content'].strip()
            score = doc.get('score', 0)
            
            logger.info(f"   📄 Match {i}: {source} p.{page} (score: {score:.3f})")
            
            # Truncate long content
            if len(content) > 400:
                content = content[:397] + "..."
            
            response_lines.append(
                f"\n**📄 Source {i}: {source}, Page {page}**\n"
                f"{content}\n"
            )
        
        final_response = "\n".join(response_lines)
        
        logger.info("=" * 80)
        logger.info(f"✅ RAG COMPLETE | Response length: {len(final_response)} chars")
        logger.info("=" * 80)
        
        return final_response
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ RAG TOOL CRITICAL ERROR")
        logger.error(f"   Error type: {type(e).__name__}")
        logger.error(f"   Error message: {str(e)}")
        logger.error(f"   Traceback:\n{traceback.format_exc()}")
        logger.error("=" * 80)
        return f"Error searching documents: {str(e)}\n\nPlease try again or contact support if the issue persists."


@tool(parse_docstring=False)
def google_web_search(query: str) -> str:
    """Search the web for current information. Use for news, facts, or recent events."""
    try:
        if google_search is None:
            return "Web search not configured"
        
        logger.info(f"🔍 Google: {query[:40]}...")
        result = google_search.run(query)
        logger.info("✅ Search complete")
        return result
    except Exception as e:
        logger.error(f"❌ Search error: {e}")
        return f"Error: {str(e)}"


@tool(parse_docstring=False)
def web_scrape(url: str) -> str:
    """Extract content from a webpage. Use when user provides a URL."""
    try:
        logger.info(f"🌐 Scraping: {url}")
        loader = WebBaseLoader(url)
        docs = loader.load()
        
        if docs:
            content = docs[0].page_content[:2000]
            logger.info(f"✅ Scraped {len(content)} chars")
            return f"Content from {url}:\n\n{content}"
        return "No content found"
        
    except Exception as e:
        logger.error(f"❌ Scrape error: {e}")
        return f"Error: {str(e)}"


def get_tools():
    """Get all tools""" 
    tools = [calculator, search_my_documents, google_web_search, web_scrape]
    logger.info(f"🔧 Registered {len(tools)} tools: {[t.name for t in tools]}")
    return tools