"""Модель сообщения диалога"""
from dataclasses import dataclass
from datetime import datetime


@dataclass
class DialogueMessage:
    """Сообщение в диалоге"""
    speaker: str  # "Speaker 1" или "Speaker 2"
    language: str  # Определенный язык (ru, en, etc)
    original_text: str
    translated_text: str
    timestamp: datetime
    confidence: float  # Уверенность распознавания
