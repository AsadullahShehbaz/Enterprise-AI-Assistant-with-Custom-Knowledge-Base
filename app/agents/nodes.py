# app/agents/nodes.py
"""
LangGraph nodes for the chatbot workflow.
"""

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.store.base import BaseStore
import uuid

from app.graph.state import ChatState
from app.agents.memory.extractor import get_memory_extractor
from app.agents.memory.prompts import MEMORY_PROMPT, CHAT_SYSTEM_PROMPT
from app.logg import logger


def remember_node(state: ChatState, config: RunnableConfig, *, store: BaseStore) -> dict:
    """
    Extract and store user memories.
    
    This node analyzes the user's message and extracts any stable personal
    information worth remembering for future conversations.
    """
    user_id = config["configurable"]["user_id"]
    ns = ("user", str(user_id), "details")
    
    # Get last user message
    last_user_msg = state["messages"][-1].content
    
    # Retrieve existing memories
    try:
        items = store.search(ns)
        existing_memories = [i.value["data"] for i in items] if items else []
        existing = "\n".join(existing_memories) if existing_memories else "(empty)"
        
        logger.info(f"📚 Current memory count: {len(existing_memories)} items")
        if existing_memories:
            logger.debug(f"   Existing memories: {existing_memories}")
    except Exception as e:
        logger.error(f"❌ Failed to retrieve existing memories: {e}")
        existing = "(empty)"
    

    try:
        # Extract memory decision
        extractor = get_memory_extractor()
        decision = extractor.extract([
            SystemMessage(content=MEMORY_PROMPT.format(user_details_content=existing)),
            {'role': 'user', 'content': last_user_msg}
        ])
        
        logger.info(f"🧠 Memory decision: should_write={decision.should_write}, new_memories={len(decision.memories)}")
        
        # Store new memories
        if decision.should_write and decision.memories:
            stored_count = 0
            for mem in decision.memories:
                if mem.is_new:
                    memory_id = str(uuid.uuid4())
                    store.put(ns, memory_id, {"data": mem.text})
                    logger.info(f"💾 Stored memory [{memory_id[:8]}]: {mem.text}")
                    stored_count += 1
                else:
                    logger.info(f"⏭️  Skipped duplicate: {mem.text}")
            
            logger.info(f"✅ Stored {stored_count} new memories")
        else:
            logger.info("ℹ️  No new memories to store")
        
    except Exception as e:
        # Don't break chat flow if memory fails
        logger.warning(f"⚠️  Memory extraction failed (non-critical): {e}")
        logger.exception("Full traceback:")
    if items:
        logger.info("\nStored Memories:")
        for i, item in enumerate(items, 1):
            logger.info(f"  {i}. [{item.key}] {item.value.get('data', 'N/A')}")
    else:
        logger.info("  (No memories stored)")

    return {}


# SOLUTION: Update how chat_node is created

# app/agents/nodes.py - Update the create_chat_node function

def create_chat_node(llm_with_tools):
    """
    Factory function to create chat node with bound LLM.
    """
    
    def chat_node(state: ChatState, config: RunnableConfig, *, store: BaseStore) -> dict:
        """Process chat with memory context and user-specific tools."""
        
        user_id_str = config["configurable"]["user_id"]
        user_id = int(user_id_str)
        ns = ("user", user_id_str, "details")
        
        logger.info(f"💬 Chat node executing for user {user_id}")
        
        # Retrieve user memory
        try:
            items = store.search(ns)
            
            # If memory variable is true then create list and save in it
            if items:
                memory_list = []

                # Loop for every item(memory) from user's namespace
                for i, item in enumerate(items, 1):
                    memory_text = item.value.get("data", "")
                    memory_list.append(f"{i}. {memory_text}") 
                
                user_memory = "\n".join(memory_list)
                logger.info(f"📖 Retrieved {len(items)} memories for user {user_id}")
            else:
                user_memory = "No information stored yet."
                logger.info(f"📭 No memories found for user {user_id}")
        
        except Exception as e:
            logger.error(f"❌ Failed to retrieve memories: {e}")
            user_memory = "(Error retrieving memory)"
        
        # Create system message with memory
        system_prompt = CHAT_SYSTEM_PROMPT.format(user_memory=user_memory)
        system_msg = SystemMessage(content=system_prompt)
        
        # IMPORTANT: Invoke LLM
        # The tools are already bound to llm_with_tools
        # LangChain will handle tool calls automatically
        try:
            response = llm_with_tools.invoke([system_msg] + state["messages"])
            logger.info(f"✅ Generated response: {len(response.content)} characters")
            
            if hasattr(response, 'tool_calls') and response.tool_calls:
                tool_names = [tc.get('name', 'unknown') for tc in response.tool_calls]
                logger.info(f"🛠️  Tools called: {', '.join(tool_names)}")
        
        except Exception as e:
            logger.error(f"❌ LLM invocation failed: {e}")
            raise
        
        return {"messages": [response]}
    
    return chat_node