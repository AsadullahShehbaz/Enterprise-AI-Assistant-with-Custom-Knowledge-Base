from pydantic import BaseModel,Field
from typing import List 

class MemoryItem(BaseModel):
    text: str
    is_new: bool 

class MemoryDecision(BaseModel):
    should_write: bool
    memories: List[MemoryItem] = Field(default_factory=list)

    