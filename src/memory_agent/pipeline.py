from memory_agent.memory_manager import MemoryManager
from memory_agent.reasoning import Reasoner


class SelectiveForgettingPipeline:
    def __init__(self) -> None:
        self.memory = MemoryManager()
        self.reasoner = Reasoner(self.memory.store)
