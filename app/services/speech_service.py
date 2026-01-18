"""Сервис для распознавания речи через Google Web Speech API"""
import speech_recognition as sr
from typing import Optional, Tuple, Callable
from app.services.translation_service import TranslationService


class SpeechService:
    """Сервис распознавания речи"""
    
    def __init__(self,
                 energy_threshold: int = 300,
                 pause_threshold: float = 0.8,
                 sample_rate: int = 16000,
                 mic_index: int = 0,
                 listen_timeout: int = 10,
                 phrase_time_limit: int = 10,
                 translation_service: Optional[TranslationService] = None,
                 message_callback: Optional[Callable] = None):
        """
        Инициализация сервиса распознавания речи
        
        Args:
            energy_threshold: Порог энергии для распознавания
            pause_threshold: Порог паузы
            sample_rate: Частота дискретизации
            mic_index: Индекс микрофона
            listen_timeout: Таймаут прослушивания
            phrase_time_limit: Максимальная длина фразы
            translation_service: Сервис перевода для определения языка
            message_callback: Функция для отправки сообщений (type, message)
        """
        self.energy_threshold = energy_threshold
        self.pause_threshold = pause_threshold
        self.sample_rate = sample_rate
        self.mic_index = mic_index
        self.listen_timeout = listen_timeout
        self.phrase_time_limit = phrase_time_limit
        self.translation_service = translation_service or TranslationService()
        self.message_callback = message_callback
        
        # Инициализация распознавателя
        self.recognizer = None
        self.microphone = None
        self.available_mics = []
        self._init_recognizer()
    
    def _init_recognizer(self):
        """Инициализация распознавателя и микрофона"""
        try:
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = self.energy_threshold
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = self.pause_threshold
            
            # Получаем список микрофонов
            print("🔍 Поиск микрофонов...")
            self.available_mics = sr.Microphone.list_microphone_names()
            if self.available_mics:
                print(f"✅ Найдено микрофонов: {len(self.available_mics)}")
                for i, mic in enumerate(self.available_mics[:3]):
                    print(f"  {i}: {mic}")
                
                try:
                    self.microphone = sr.Microphone(
                        device_index=self.mic_index,
                        sample_rate=self.sample_rate
                    )
                    print(f"✅ Выбран микрофон: {self.available_mics[self.mic_index]}")
                except Exception as e:
                    print(f"⚠️ Ошибка выбора микрофона: {e}")
                    self.microphone = None
            else:
                print("⚠️ Микрофоны не найдены")
                self.microphone = None
        
        except Exception as e:
            print(f"❌ Ошибка инициализации распознавания: {e}")
            self.recognizer = None
            self.microphone = None
    
    def get_language_code(self, display_text: str) -> Tuple[str, str]:
        """
        Получает код языка из отображаемого текста
        
        Args:
            display_text: Отображаемый текст (например, '🇷🇺 RU')
            
        Returns:
            Кортеж (код_перевода, код_распознавания)
        """
        from app.config import LANGUAGE_MAP
        return LANGUAGE_MAP.get(display_text, ('en', 'en-US'))
    
    def recognize_audio(self, audio, lang1_display: str, lang2_display: str) -> Tuple[Optional[str], Optional[str], float]:
        """
        Распознает аудио через Google Web Speech API
        
        Args:
            audio: Аудио объект от speech_recognition
            lang1_display: Отображаемый текст первого языка
            lang2_display: Отображаемый текст второго языка
            
        Returns:
            Кортеж (текст, определенный_язык, уверенность) или (None, None, 0.0)
        """
        try:
            # Получаем языки для распознавания
            lang1_trans, lang1_speech = self.get_language_code(lang1_display)
            lang2_trans, lang2_speech = self.get_language_code(lang2_display)
            
            text = None
            detected_lang = None
            confidence = 0.8
            
            # Автоопределение языка
            if self.message_callback:
                self.message_callback('status', f"🔍 Определяю язык...")
            
            # Сначала пробуем автоопределение Google
            try:
                text = self.recognizer.recognize_google(audio, show_all=False)
                if text:
                    # Пытаемся определить язык текста
                    detected_lang = self.translation_service.detect_language_from_text(text)
                    if not detected_lang:
                        # Если не удалось определить, используем первый язык
                        detected_lang = lang1_trans
                    if self.message_callback:
                        self.message_callback('info', f"🌍 Определен язык: {detected_lang}")
            except sr.UnknownValueError:
                pass
            
            if not text:
                # Пробуем поочередно каждый язык
                languages_to_try = [
                    (lang1_trans, lang1_speech),
                    (lang2_trans, lang2_speech)
                ]
                
                for lang_trans, lang_speech in languages_to_try:
                    try:
                        text = self.recognizer.recognize_google(audio, language=lang_speech)
                        detected_lang = lang_trans
                        if self.message_callback:
                            self.message_callback('info', f"✅ Определен язык: {detected_lang}")
                        break
                    except sr.UnknownValueError:
                        continue
            
            if text and detected_lang:
                return text, detected_lang, confidence
            else:
                raise sr.UnknownValueError("Речь не распознана")
        
        except sr.UnknownValueError:
            raise
        except sr.RequestError as e:
            raise
        except Exception as e:
            print(f"❌ Ошибка распознавания: {e}")
            raise
    
    def adjust_for_ambient_noise(self, duration: float = 0.5):
        """
        Калибрует микрофон для фонового шума
        
        Args:
            duration: Длительность калибровки
        """
        if self.microphone and self.recognizer:
            try:
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=duration)
                print("✅ Микрофон откалиброван")
            except Exception as e:
                print(f"⚠️ Ошибка калибровки: {e}")
    
    def listen(self):
        """
        Слушает микрофон и возвращает аудио
        
        Returns:
            Аудио объект
            
        Raises:
            sr.WaitTimeoutError: Таймаут прослушивания
            sr.UnknownValueError: Речь не распознана
            sr.RequestError: Ошибка API
        """
        if not self.microphone or not self.recognizer:
            raise RuntimeError("Микрофон или распознаватель не инициализирован")
        
        with self.microphone as source:
            audio = self.recognizer.listen(
                source,
                timeout=self.listen_timeout,
                phrase_time_limit=self.phrase_time_limit
            )
        return audio
