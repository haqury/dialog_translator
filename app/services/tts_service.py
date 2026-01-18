"""Сервис для озвучивания текста через ElevenLabs TTS"""
import threading
import tempfile
import time
import requests
from typing import Callable, Optional
from app.config import TTS_VOICES


class TTSService:
    """Сервис озвучивания текста через ElevenLabs"""
    
    def __init__(self, 
                 api_key: str,
                 model: str = 'eleven_turbo_v2',
                 speed: float = 1.0,
                 default_voice_id: str = 'CwhRBWXzGAHq8TQ4Fs17',
                 message_callback: Optional[Callable] = None):
        """
        Инициализация TTS сервиса
        
        Args:
            api_key: API ключ ElevenLabs
            model: Модель TTS (eleven_turbo_v2, eleven_multilingual_v2)
            speed: Скорость речи
            default_voice_id: ID голоса по умолчанию
            message_callback: Функция для отправки сообщений (type, message)
        """
        self.api_key = api_key
        # Автоматическая миграция устаревших моделей
        deprecated_models = ['eleven_multilingual_v1', 'eleven_monolingual_v1']
        if model in deprecated_models:
            print(f"⚠️ Обнаружена устаревшая модель TTS: {model}")
            print("   Автоматически заменяю на eleven_turbo_v2")
            self.model = 'eleven_turbo_v2'
        else:
            self.model = model
        self.speed = speed
        self.default_voice_id = default_voice_id
        self.message_callback = message_callback
    
    def get_voice_for_language(self, lang: str) -> str:
        """
        Получает ID голоса для языка
        
        Args:
            lang: Код языка (ru, en, es, fr, de)
            
        Returns:
            ID голоса
        """
        return TTS_VOICES.get(lang, self.default_voice_id)
    
    def speak(self, text: str, source_lang: str = "en", callback: Optional[Callable] = None):
        """
        Озвучивает текст асинхронно
        
        Args:
            text: Текст для озвучивания
            source_lang: Язык текста
            callback: Функция для получения пути к аудио файлу (file_path)
        """
        if not text.strip():
            return
        
        if not self.api_key:
            if self.message_callback:
                self.message_callback('error', "❌ ElevenLabs API ключ не установлен")
            return
        
        # Определяем голос в зависимости от языка
        voice_id = self.get_voice_for_language(source_lang)
        
        # Запускаем в отдельном потоке
        threading.Thread(
            target=self._tts_worker,
            args=(text, voice_id, callback),
            daemon=True
        ).start()
    
    def _tts_worker(self, text: str, voice_id: str, callback: Optional[Callable]):
        """Рабочий поток для работы с ElevenLabs API"""
        try:
            if self.message_callback:
                self.message_callback('status', "🔊 Озвучивание...")
            
            # Подробная отладка
            print(f"\n" + "=" * 60)
            print(f"🔊 DEBUG: Запуск ElevenLabs TTS")
            print(f"🔊 DEBUG: Текст: '{text[:50]}...'")
            print(f"🔊 DEBUG: Voice ID: {voice_id}")
            print(f"🔊 DEBUG: Ключ: {self.api_key[:10]}...")
            print("=" * 60)
            
            # Проверяем наличие ключа
            api_key = self.api_key.strip()
            if not api_key:
                error_msg = "❌ API ключ ElevenLabs не установлен"
                print(f"❌ DEBUG: {error_msg}")
                if self.message_callback:
                    self.message_callback('error', error_msg)
                return
            
            # Проверяем формат ключа
            if not api_key.startswith("sk_"):
                error_msg = "❌ Неверный формат ключа (должен начинаться с 'sk_')"
                print(f"❌ DEBUG: {error_msg}")
                if self.message_callback:
                    self.message_callback('error', error_msg)
                return
            
            # Подготовка данных для запроса
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
                    "speed": self.speed,
                    "use_speaker_boost": True
                }
            }
            
            print(f"🔊 DEBUG: Отправляю запрос на {url}")
            print(f"🔊 DEBUG: Заголовки: {headers}")
            print(f"🔊 DEBUG: Данные: {data}")
            
            # Выполняем запрос с таймаутом
            start_time = time.time()
            
            try:
                response = requests.post(url, json=data, headers=headers, timeout=30)
                elapsed_time = time.time() - start_time
                
                print(f"🔊 DEBUG: Ответ получен за {elapsed_time:.2f} сек")
                print(f"🔊 DEBUG: Статус: {response.status_code}")
                print(f"🔊 DEBUG: Размер ответа: {len(response.content) if response.content else 0} байт")
            
            except requests.exceptions.Timeout:
                error_msg = "❌ Таймаут при озвучивании (30 сек)"
                print(f"❌ DEBUG: {error_msg}")
                if self.message_callback:
                    self.message_callback('error', error_msg)
                return
            
            except requests.exceptions.RequestException as e:
                error_msg = f"❌ Ошибка сети: {str(e)[:50]}"
                print(f"❌ DEBUG: {error_msg}")
                if self.message_callback:
                    self.message_callback('error', error_msg)
                return
            
            if response.status_code == 200:
                if response.content:
                    # Сохраняем аудио во временный файл
                    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                        f.write(response.content)
                        temp_file = f.name
                    
                    print(f"🔊 DEBUG: Аудио сохранено в {temp_file}")
                    print(f"🔊 DEBUG: Размер файла: {len(response.content)} байт")
                    
                    # Вызываем callback с путем к файлу
                    if callback:
                        callback(temp_file)
                    
                    if self.message_callback:
                        self.message_callback('info', "✅ Озвучивание успешно")
                else:
                    error_msg = "❌ Пустой ответ от сервера"
                    print(f"❌ DEBUG: {error_msg}")
                    if self.message_callback:
                        self.message_callback('error', error_msg)
            
            elif response.status_code == 401:
                error_detail = ""
                try:
                    error_data = response.json()
                    print(f"❌ DEBUG: 401 ошибка JSON: {error_data}")
                    if isinstance(error_data, dict) and 'detail' in error_data:
                        detail = error_data['detail']
                        if isinstance(detail, dict):
                            error_detail = detail.get('message', str(detail))
                        else:
                            error_detail = str(detail)
                except:
                    error_detail = response.text[:100] if response.text else ""
                    print(f"❌ DEBUG: 401 ошибка текст: {error_detail}")
                
                error_msg = f"❌ Неверный API ключ или модель устарела"
                print(f"❌ DEBUG: {error_msg}")
                if self.message_callback:
                    self.message_callback('error', error_msg)
            
            elif response.status_code == 402:
                error_msg = "❌ Закончились бесплатные символы"
                print(f"❌ DEBUG: {error_msg}")
                if self.message_callback:
                    self.message_callback('error', error_msg)
            
            elif response.status_code == 422:
                try:
                    error_data = response.json()
                    print(f"❌ DEBUG: 422 ошибка: {error_data}")
                    if isinstance(error_data, dict) and 'detail' in error_data:
                        error_detail = str(error_data['detail'])
                    else:
                        error_detail = str(error_data)
                    error_msg = f"❌ Ошибка валидации: {error_detail[:50]}"
                except:
                    error_msg = f"❌ Ошибка 422: {response.text[:50] if response.text else 'Validation error'}"
                print(f"❌ DEBUG: {error_msg}")
                if self.message_callback:
                    self.message_callback('error', error_msg)
            
            elif response.status_code == 429:
                error_msg = "❌ Слишком много запросов. Попробуйте позже"
                print(f"❌ DEBUG: {error_msg}")
                if self.message_callback:
                    self.message_callback('error', error_msg)
            
            else:
                error_msg = ""
                try:
                    error_data = response.json()
                    print(f"❌ DEBUG: {response.status_code} ошибка JSON: {error_data}")
                    if isinstance(error_data, dict):
                        if 'detail' in error_data:
                            detail = error_data['detail']
                            if isinstance(detail, dict):
                                error_msg = detail.get('message', str(detail))
                            else:
                                error_msg = str(detail)
                        else:
                            error_msg = str(error_data)
                    else:
                        error_msg = str(error_data)
                except:
                    error_msg = response.text[:100] if response.text else f"HTTP {response.status_code}"
                    print(f"❌ DEBUG: {response.status_code} ошибка текст: {error_msg}")
                
                error_msg = f"❌ ElevenLabs ошибка: {error_msg[:50]}"
                print(f"❌ DEBUG: {error_msg}")
                if self.message_callback:
                    self.message_callback('error', error_msg)
            
            print(f"🔊 DEBUG: Конец TTS запроса")
            print("=" * 60 + "\n")
        
        except Exception as e:
            import traceback
            print(f"❌ DEBUG: Неожиданная ошибка: {e}")
            print(f"❌ DEBUG: Traceback: {traceback.format_exc()}")
            if self.message_callback:
                self.message_callback('error', f"❌ Ошибка озвучивания: {str(e)[:50]}")
