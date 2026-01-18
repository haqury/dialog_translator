"""Провайдер Google Cloud TTS"""
import threading
import tempfile
import requests
import base64
from typing import Callable, Optional
from .base_provider import BaseTTSProvider


class GoogleCloudProvider(BaseTTSProvider):
    """Провайдер озвучивания через Google Cloud TTS"""
    
    def __init__(self, 
                 api_key: str,
                 project_id: str = '',
                 default_voice: str = 'ru-RU-Standard-A',
                 message_callback: Optional[Callable] = None):
        super().__init__(api_key, message_callback)
        self.project_id = project_id
        self.default_voice = default_voice
    
    def speak(self, text: str, source_lang: str = "en", 
              voice_id: Optional[str] = None,
              speed: float = 1.0,
              volume: int = 80,
              callback: Optional[Callable] = None):
        """Озвучивает текст через Google Cloud TTS"""
        if not text.strip():
            return
        
        if not self.api_key:
            if self.message_callback:
                self.message_callback('error', "❌ Google Cloud API ключ не установлен")
            return
        
        voice_name = voice_id or self.default_voice
        
        threading.Thread(
            target=self._tts_worker,
            args=(text, voice_name, speed, volume, callback),
            daemon=True
        ).start()
    
    def _tts_worker(self, text: str, voice_name: str, speed: float, volume: int, callback: Optional[Callable]):
        """Рабочий поток для Google Cloud TTS"""
        try:
            if self.message_callback:
                self.message_callback('status', "🔊 Озвучивание через Google Cloud...")
            
            # Google Cloud TTS REST API
            # Используем API ключ через query parameter или OAuth токен
            url = "https://texttospeech.googleapis.com/v1/text:synthesize"
            
            # Определяем язык из имени голоса (например, ru-RU-Standard-A -> ru-RU)
            if '-' in voice_name:
                parts = voice_name.split('-')
                language_code = f"{parts[0]}-{parts[1]}"
            else:
                language_code = "en-US"
            
            headers = {
                "Content-Type": "application/json"
            }
            
            # Используем API ключ через query parameter
            params = {"key": self.api_key}
            
            data = {
                "input": {"text": text},
                "voice": {
                    "languageCode": language_code,
                    "name": voice_name
                },
                "audioConfig": {
                    "audioEncoding": "MP3",
                    "speakingRate": speed,
                    "volumeGainDb": (volume - 50) * 0.5  # Преобразуем 0-100 в dB
                }
            }
            
            response = requests.post(url, json=data, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                audio_content = result.get('audioContent', '')
                if audio_content:
                    audio_data = base64.b64decode(audio_content)
                    print(f"🔊 DEBUG: Google Cloud: получено {len(audio_data)} байт аудио")
                    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                        f.write(audio_data)
                        temp_file = f.name
                    
                    if callback:
                        callback(temp_file)
                    
                    if self.message_callback:
                        self.message_callback('info', "✅ Озвучивание успешно")
                else:
                    if self.message_callback:
                        self.message_callback('error', "❌ Пустой ответ от сервера")
            elif response.status_code == 403:
                # Пытаемся извлечь более понятное сообщение об ошибке
                try:
                    error_data = response.json()
                    error_detail = error_data.get('error', {})
                    error_message = error_detail.get('message', '')
                    if 'not been used' in error_message or 'disabled' in error_message:
                        error_msg = "❌ Google Cloud TTS API не включен в проекте.\nВключите API в Google Cloud Console:\nhttps://console.cloud.google.com/apis/library/texttospeech.googleapis.com"
                    else:
                        error_msg = f"❌ Google Cloud ошибка доступа (403): {error_message[:100]}"
                except:
                    error_msg = "❌ Google Cloud ошибка доступа (403). Проверьте, что API включен в проекте."
                print(f"❌ DEBUG: {error_msg}")
                if self.message_callback:
                    self.message_callback('error', error_msg)
            elif response.status_code == 401:
                error_msg = "❌ Неверный API ключ Google Cloud"
                print(f"❌ DEBUG: {error_msg}")
                if self.message_callback:
                    self.message_callback('error', error_msg)
            else:
                error_text = response.text[:200] if response.text else ""
                try:
                    error_data = response.json()
                    error_detail = error_data.get('error', {})
                    error_message = error_detail.get('message', error_text)
                    error_msg = f"❌ Google Cloud ошибка {response.status_code}: {error_message[:100]}"
                except:
                    error_msg = f"❌ Google Cloud ошибка {response.status_code}: {error_text}"
                print(f"❌ DEBUG: {error_msg}")
                if self.message_callback:
                    self.message_callback('error', error_msg)
        
        except Exception as e:
            print(f"❌ DEBUG: Google Cloud TTS ошибка: {e}")
            if self.message_callback:
                self.message_callback('error', f"❌ Ошибка: {str(e)[:50]}")
    
    def get_voices(self) -> list:
        """Получает список доступных голосов"""
        if not self.api_key:
            return []
        
        try:
            url = "https://texttospeech.googleapis.com/v1/voices"
            params = {"key": self.api_key}
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                voices = data.get('voices', [])
                # Преобразуем в формат, похожий на ElevenLabs
                result = []
                for voice in voices:
                    result.append({
                        'voice_id': voice.get('name', ''),
                        'name': voice.get('name', ''),
                        'description': f"{voice.get('ssmlGender', '')} - {', '.join(voice.get('languageCodes', []))}"
                    })
                return result
        except Exception as e:
            print(f"❌ Ошибка получения голосов Google Cloud: {e}")
        
        return []
