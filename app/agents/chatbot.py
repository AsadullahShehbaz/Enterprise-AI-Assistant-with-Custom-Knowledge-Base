# app/agents/chatbot.py
import time
from typing import Dict, Any,AsyncGenerator
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
import asyncio

from app.config import get_settings
from app.logg import logger
from app.agents.tools import get_tools
from app.graph.builder import GraphBuilder
from app.context.user_context import set_current_user_id
from app.infrastructure.database import DatabaseResources


class ChatbotAgent:
    """
    Main chatbot agent with long-term memory and RAG capabilities.
    
    This agent manages:
    - LLM interaction (ChatGroq)
    - Tool execution (calculator, web search, RAG)
    - Memory persistence (PostgreSQL)
    - Graph execution (LangGraph)
    """
    
    def __init__(self):
        logger.info("🚀 Initializing ChatbotAgent...")
        
        settings = get_settings()
        
        # --------------------------
        # 1️⃣ Setup LLM
        # --------------------------
        logger.info("🤖 Initializing ChatGroq LLM...")
        self.llm = ChatGroq(
            model="openai/gpt-oss-120b",
            temperature=0.7,
            api_key=settings.GROQ_API_KEY
        )
        
        # --------------------------
        # 2️⃣ Setup Tools
        # --------------------------
        logger.info("🛠️  Loading tools...")
        self.tools = get_tools()
        logger.info(f"✅ Loaded {len(self.tools)} tools")
        
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        
        # --------------------------
        # 3️⃣ Initialize Database Resources
        # --------------------------
        logger.info("📊 Initializing database resources...")
        self.db_resources = DatabaseResources()
        
        # Enter the context manager
        self.checkpointer, self.store = self.db_resources.__enter__()
        
        # --------------------------
        # 4️⃣ Build Graph
        # --------------------------
        logger.info("🧩 Building LangGraph workflow...")
        builder = GraphBuilder(self.llm_with_tools, self.tools)
        self.graph = builder.build(self.checkpointer, self.store)
        
        logger.info("✅ ChatbotAgent initialization complete")
    

    async def chat_stream(
            self, 
            message: str, 
            user_id: int, 
            thread_id: int
    )->AsyncGenerator[dict,None]:  # ← Removed return type (generators don't have one)
            """Stream chat responses with tool visibility."""
            
            logger.info("─" * 60)
            logger.info(f"🌊 Starting STREAM | user_id={user_id} | thread_id={thread_id}")
            logger.debug(f"📝 User message: {message[:100]}...")
            
            # Set user context
            set_current_user_id(user_id)
            
            # Prepare config
            config = {
                "configurable": {
                    "thread_id": f"user_{user_id}_thread_{thread_id}",
                    "user_id": str(user_id)
                }
            }
            yield {
                "type":"status",
                "step":"memory",
                "status":"retrieving",
                "message":"🧠 Retrieving your memory..."
            }

            logger.info("📋 Stream config:")
            logger.info(f"   thread_id: {config['configurable']['thread_id']}")
            logger.info(f"   user_id: {config['configurable']['user_id']}")
            
            try:
                start_time = time.time()
                logger.info("🔄 Starting graph astream...")
                
                def sync_stream():
                    for chunk in self.graph.stream(
                        {"messages":[HumanMessage(content=message)]},
                        config=config,
                        stream_mode="messages"
                    ):
                        
                        yield chunk 
                loop = asyncio.get_event_loop() 

                for chunk in sync_stream():

                    await asyncio.sleep(0)
                    msg,metadata = chunk 
                    node = metadata.get("langgraph_node")

                    logger.debug(f"📦 Node: {node} | Type: {type(msg).__name__}")
                    if node == "remember":
                        continue
                    
                    elif node == "chat_node":
                        if hasattr(msg,'content') and msg.content:

                            if not hasattr(self,'_generation_started'):
                                self._generation_started = True

                                yield {
                                    "type":"status",
                                    "step":"generation",
                                    "status":"started",
                                    "message":"✍️ Generating response..."
                                }
                            yield {
                                'type':'content',
                                'data':msg.content
                            }
                    
                    elif node == "tools":
                        if hasattr(msg,"name"):
                            tool_name = msg.name
                            yield {
                                "type":"tool_start",
                                "tool": tool_name,
                                "status":f"Using {tool_name}..."
                            }

                        # Tool result (has content)
                        if hasattr(msg, 'content') and msg.content:
                            logger.debug(f"   ✅ Tool result: {msg.content[:50]}...")
                            yield {
                                "type": "tool_complete",
                                "tool": getattr(msg,'name','unknown'),
                                "message": "✅ Tool execution complete"  # Truncate long results
                            }
                
                # Reset flag for next stream
                if hasattr(self, '_generation_started'):
                    delattr(self, '_generation_started')
                execution_time = time.time() - start_time
                logger.info(f"✅ Stream completed in {execution_time:.2f}s")
                
            except Exception as e:
                logger.exception(f"❌ Stream failed | user_id={user_id}")
                yield {
                    "type": "error",
                    "message": str(e)
                }
    async def get_thread_history(self,user_id: int, thread_id: int) -> list:
   
        config = {
            "configurable": {
                "thread_id": f"user_{user_id}_thread_{thread_id}",
                "user_id": str(user_id)  # CRITICAL: Must be string for LangGraph
            }
        }

        try:
            # Get state from checkpointer
            state = self.graph.get_state(config)

            if not state or not state.values.get("messages"):
                logger.info(f"No history found for thread {thread_id}")
                return []

            messages = state.values["messages"]
            logger.info(f"Retreived {len(messages)} messages for thread {thread_id}")

            # Format messages for Frontend 
            history = []
            for msg in messages:
                if hasattr(msg,'type'):
                    if msg.type =='human':
                        history.append({'role':'user','content':msg.content})
                    elif msg.type =='ai':
                        history.append({'role':'assistant','content':msg.content})
            return history 
        except Exception as e:
            logger.error(f"❌ Error getting thread history: {e}")
            return [] 
    def cleanup(self):
        """
        Cleanup database resources.
        
        IMPORTANT: Must be called on application shutdown!
        """
        logger.info("🧹 Cleaning up ChatbotAgent resources...")
        
        try:
            self.db_resources.__exit__(None, None, None)
            logger.info("✅ ChatbotAgent cleanup complete")
        except Exception as e:
            logger.error(f"⚠️  Error during cleanup: {e}")


# --------------------------
# Singleton Pattern
# --------------------------
_chatbot_agent = None


async def get_chatbot_agent() -> ChatbotAgent:
    """
    Get or create the chatbot agent singleton.
    
    Returns:
        ChatbotAgent instance
    """
    global _chatbot_agent
    
    if _chatbot_agent is None:
        logger.info("🧠 Creating ChatbotAgent singleton...")
        _chatbot_agent = ChatbotAgent()
    
    return _chatbot_agent


def cleanup_chatbot_agent():
    """
    Cleanup the chatbot agent singleton.
    
    Should be called on application shutdown.
    """
    global _chatbot_agent
    
    if _chatbot_agent is not None:
        logger.info("🗑️  Destroying ChatbotAgent singleton...")
        _chatbot_agent.cleanup()
        _chatbot_agent = None
        logger.info("✅ ChatbotAgent singleton destroyed")