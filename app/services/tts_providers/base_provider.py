"""Базовый класс для TTS провайдеров"""
from abc import ABC, abstractmethod
from typing import Optional, Callable


class BaseTTSProvider(ABC):
    """Базовый класс для всех TTS провайдеров"""
    
    def __init__(self, 
                 api_key: str,
                 message_callback: Optional[Callable] = None):
        """
        Инициализация провайдера
        
        Args:
            api_key: API ключ провайдера
            message_callback: Функция для отправки сообщений (type, message)
        """
        self.api_key = api_key
        self.message_callback = message_callback
    
    @abstractmethod
    def speak(self, text: str, source_lang: str = "en", 
              voice_id: Optional[str] = None,
              speed: float = 1.0,
              volume: int = 80,
              callback: Optional[Callable] = None):
        """
        Озвучивает текст асинхронно
        
        Args:
            text: Текст для озвучивания
            source_lang: Язык текста
            voice_id: ID голоса (опционально)
            speed: Скорость речи (0.5-2.0)
            volume: Громкость (0-100)
            callback: Функция для получения пути к аудио файлу (file_path)
        """
        pass
    
    @abstractmethod
    def get_voices(self) -> list:
        """
        Получает список доступных голосов
        
        Returns:
            Список словарей с информацией о голосах
        """
        pass
    
    def validate_api_key(self):
        """
        Проверяет валидность API ключа
        
        Returns:
            (is_valid, error_message)
        """
        if not self.api_key or not self.api_key.strip():
            return False, "API ключ не установлен"
        return True, ""
