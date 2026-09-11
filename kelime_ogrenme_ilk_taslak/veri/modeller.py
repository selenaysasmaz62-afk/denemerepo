from dataclasses import dataclass

@dataclass
class LearningWord:
    id: int
    word: str
    normalized_word: str
    status: str
    current_step: str
