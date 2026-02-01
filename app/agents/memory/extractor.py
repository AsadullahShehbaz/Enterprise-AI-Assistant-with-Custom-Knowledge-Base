# app/agents/memory/extractor.py
from langchain_groq import ChatGroq
from app.agents.memory.models import MemoryDecision
from app.config import get_settings
from app.logg import logger 

class MemoryExtractor:
    """Handles memory extraction from conversations."""
    
    def __init__(self):
        settings = get_settings()
        self.llm = ChatGroq(
            model='openai/gpt-oss-120b',
            api_key=settings.GROQ_API_KEY,
            temperature=0
        )
        # Create the structured output chain
        self.extractor_chain = self.llm.with_structured_output(MemoryDecision)
    
    def extract(self, messages: list) -> MemoryDecision:
        """
        Extract memory decision from messages.
        
        Args:
            messages: List of messages to extract memory from
            
        Returns:
            MemoryDecision with should_write and memories
        """
        try:
            return self.extractor_chain.invoke(messages)
        except Exception as e:
            logger.warning(f"⚠️  Memory extraction failed: {e}")
            return MemoryDecision(should_write=False, memories=[])


_memory_extractor = None 


def get_memory_extractor() -> MemoryExtractor:
    """Get singleton memory extractor."""
    global _memory_extractor
    if _memory_extractor is None:
        _memory_extractor = MemoryExtractor()
    return _memory_extractor