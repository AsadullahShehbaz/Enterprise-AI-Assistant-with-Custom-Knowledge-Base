# app/graph/builder.py
from langgraph.graph import StateGraph, START
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore

from app.graph.state import ChatState
from app.agents.nodes import remember_node, create_chat_node
from app.logg import logger


class GraphBuilder:
    """Builds the LangGraph workflow with memory and tools."""
    
    def __init__(self, llm_with_tools, tools):
        self.llm_with_tools = llm_with_tools
        self.tools = tools
    
    def build(
        self, 
        checkpointer: PostgresSaver, 
        store: PostgresStore
    ) -> StateGraph:
        """
        Construct and compile the graph with provided database resources.
        
        Args:
            checkpointer: PostgresSaver instance from DatabaseResources
            store: PostgresStore instance from DatabaseResources
            
        Returns:
            Compiled StateGraph ready for invocation
        """
        logger.info("🧩 Building LangGraph workflow...")
        
        # Create state graph
        graph = StateGraph(ChatState)
        
        # Create nodes
        logger.info("📦 Creating chat node...")
        chat_node = create_chat_node(self.llm_with_tools)
        
        logger.info("🛠️  Creating tool node with config passing...")
        # IMPORTANT: ToolNode automatically passes config to tools with InjectedToolArg
        tool_node = ToolNode(self.tools)
        
        # Log tool information
        logger.info(f"   Tools in ToolNode: {[t.name for t in self.tools]}")
        for tool in self.tools:
            logger.info(f"   - {tool.name}: {tool.description[:60]}...")
        
        # Add nodes to graph
        logger.info("➕ Adding nodes to graph...")
        graph.add_node("remember", remember_node)
        graph.add_node("chat_node", chat_node)
        graph.add_node("tools", tool_node)
        
        # Define edges
        logger.info("🔗 Defining graph edges...")
        graph.add_edge(START, "remember")
        graph.add_edge("remember", "chat_node")
        graph.add_conditional_edges("chat_node", tools_condition)
        graph.add_edge("tools", "chat_node")
        
        # Compile with checkpointer and store
        logger.info("⚙️  Compiling graph with checkpointer and store...")
        compiled_graph = graph.compile(
            checkpointer=checkpointer, 
            store=store
        )
        
        logger.info("✅ Graph compilation complete")
        logger.info("   Graph will pass config to all nodes automatically")
        
        return compiled_graph