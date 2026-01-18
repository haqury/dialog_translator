"""Провайдер ElevenLabs TTS"""
import threading
import tempfile
import time
import requests
from typing import Callable, Optional
from .base_provider import BaseTTSProvider
from app.config import TTS_VOICES


class ElevenLabsProvider(BaseTTSProvider):
    """Провайдер озвучивания через ElevenLabs"""
    
    def __init__(self, 
                 api_key: str,
                 model: str = 'eleven_turbo_v2',
                 default_voice_id: str = 'CwhRBWXzGAHq8TQ4Fs17',
                 message_callback: Optional[Callable] = None):
        """
        Инициализация провайдера ElevenLabs
        
        Args:
            api_key: API ключ ElevenLabs
            model: Модель TTS (eleven_turbo_v2, eleven_multilingual_v2)
            default_voice_id: ID голоса по умолчанию
            message_callback: Функция для отправки сообщений (type, message)
        """
        super().__init__(api_key, message_callback)
        # Автоматическая миграция устаревших моделей
        deprecated_models = ['eleven_multilingual_v1', 'eleven_monolingual_v1']
        if model in deprecated_models:
            print(f"⚠️ Обнаружена устаревшая модель TTS: {model}")
            print("   Автоматически заменяю на eleven_turbo_v2")
            self.model = 'eleven_turbo_v2'
        else:
            self.model = model
        self.default_voice_id = default_voice_id
    
    def get_voice_for_language(self, lang: str) -> str:
        """Получает ID голоса для языка"""
        return TTS_VOICES.get(lang, self.default_voice_id)
    
    def speak(self, text: str, source_lang: str = "en", 
              voice_id: Optional[str] = None,
              speed: float = 1.0,
              volume: int = 80,
              callback: Optional[Callable] = None):
        """Озвучивает текст асинхронно"""
        print(f"🔊 DEBUG: ElevenLabsProvider.speak() вызван")
        print(f"🔊 DEBUG: Текст: '{text[:50]}...', voice_id: {voice_id}, speed: {speed}, volume: {volume}")
        
        if not text.strip():
            print(f"❌ DEBUG: Текст пустой в speak()")
            return
        
        if not self.api_key:
            error_msg = "❌ ElevenLabs API ключ не установлен"
            print(f"❌ DEBUG: {error_msg}")
            if self.message_callback:
                self.message_callback('error', error_msg)
            return
        
        # Определяем голос
        if not voice_id:
            voice_id = self.get_voice_for_language(source_lang)
            print(f"🔊 DEBUG: Voice ID определен автоматически: {voice_id}")
        
        print(f"🔊 DEBUG: Запускаю поток _tts_worker с voice_id={voice_id}")
        # Запускаем в отдельном потоке
        threading.Thread(
            target=self._tts_worker,
            args=(text, voice_id, speed, callback),
            daemon=True
        ).start()
        print(f"🔊 DEBUG: Поток _tts_worker запущен")
    
    def _tts_worker(self, text: str, voice_id: str, speed: float, callback: Optional[Callable]):
        """Рабочий поток для работы с ElevenLabs API"""
        try:
            if self.message_callback:
                self.message_callback('status', "🔊 Озвучивание...")
            
            api_key = self.api_key.strip()
            if not api_key:
                error_msg = "❌ API ключ ElevenLabs не установлен"
                if self.message_callback:
                    self.message_callback('error', error_msg)
                return
            
            if not api_key.startswith("sk_"):
                error_msg = "❌ Неверный формат ключа (должен начинаться с 'sk_')"
                if self.message_callback:
                    self.message_callback('error', error_msg)
                return
            
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": api_key
            }
            
            data = {
                "text": text,
                "model_id": self.model,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.5,
                    "speed": speed,
                    "use_speaker_boost": True
                }
            }
            
            response = requests.post(url, json=data, headers=headers, timeout=30)
            
            if response.status_code == 200:
                if response.content:
                    print(f"🔊 DEBUG: Получен аудио контент, размер: {len(response.content)} байт")
                    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                        f.write(response.content)
                        temp_file = f.name
                    print(f"🔊 DEBUG: Аудио сохранено в: {temp_file}")
                    
                    if callback:
                        print(f"🔊 DEBUG: Вызываю callback с файлом: {temp_file}")
                        callback(temp_file)
                    else:
                        print(f"⚠️ DEBUG: Callback не установлен!")
                    
                    if self.message_callback:
                        self.message_callback('info', "✅ Озвучивание успешно")
                else:
                    if self.message_callback:
                        self.message_callback('error', "❌ Пустой ответ от сервера")
            elif response.status_code == 401:
                error_msg = "❌ Неверный API ключ или модель устарела"
                if self.message_callback:
                    self.message_callback('error', error_msg)
            elif response.status_code == 402:
                error_msg = "❌ Закончились бесплатные символы"
                if self.message_callback:
                    self.message_callback('error', error_msg)
            else:
                error_msg = f"❌ ElevenLabs ошибка: {response.status_code}"
                if self.message_callback:
                    self.message_callback('error', error_msg)
        
        except Exception as e:
            if self.message_callback:
                self.message_callback('error', f"❌ Ошибка озвучивания: {str(e)[:50]}")
    
    def get_voices(self) -> list:
        """Получает список доступных голосов из ElevenLabs API"""
        if not self.api_key or not self.api_key.strip():
            return []
        
        try:
            url = "https://api.elevenlabs.io/v1/voices"
            headers = {"xi-api-key": self.api_key}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('voices', [])
        except Exception as e:
            print(f"❌ Ошибка получения голосов ElevenLabs: {e}")
        
        return []
