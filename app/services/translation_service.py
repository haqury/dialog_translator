"""Сервис для перевода текста через Google Translate API"""
import requests
from typing import Optional


class TranslationService:
    """Сервис перевода текста"""
    
    def __init__(self, timeout: int = 5):
        """
        Инициализация сервиса перевода
        
        Args:
            timeout: Таймаут запроса в секундах
        """
        self.timeout = timeout
    
    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Переводит текст через Google Translate API
        
        Args:
            text: Текст для перевода
            source_lang: Исходный язык (ru, en, etc)
            target_lang: Целевой язык (ru, en, etc)
            
        Returns:
            Переведенный текст или сообщение об ошибке
        """
        if source_lang == target_lang:
            return text
        
        try:
            url = "https://translate.googleapis.com/translate_a/single"
            
            params = {
                'client': 'gtx',
                'sl': source_lang,
                'tl': target_lang,
                'dt': 't',
                'q': text
            }
            
            response = requests.get(
                url,
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                translated_parts = []
                if data and len(data) > 0 and data[0]:
                    for item in data[0]:
                        if item and len(item) > 0:
                            translated_parts.append(item[0])
                
                return ' '.join(translated_parts) if translated_parts else text
            else:
                print(f"❌ Ошибка перевода: HTTP {response.status_code}")
                return f"[Ошибка перевода]"
        
        except requests.exceptions.Timeout:
            print("❌ Таймаут при переводе")
            return f"[Таймаут перевода]"
        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка сети при переводе: {e}")
            return f"[Ошибка сети]"
        except Exception as e:
            print(f"❌ Ошибка перевода: {e}")
            return f"[Ошибка перевода]"
    
    def detect_language_from_text(self, text: str) -> Optional[str]:
        """
        Пытается определить язык текста по содержимому
        
        Args:
            text: Текст для определения языка
            
        Returns:
            Код языка (ru, en, es, fr, de) или None
        """
        try:
            text_lower = text.lower()
            
            # Проверяем русские символы
            if any(cyr_char in text_lower for cyr_char in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'):
                return 'ru'
            
            # Проверяем английские слова
            common_english_words = ['the', 'and', 'you', 'that', 'was', 'for', 'are', 'with', 'this', 'have']
            if any(word in text_lower for word in common_english_words):
                return 'en'
            
            # Проверяем испанские символы
            if any(span_char in text_lower for span_char in 'áéíóúñ'):
                return 'es'
            
            # Проверяем французские символы
            if any(french_char in text_lower for french_char in 'àâäçéèêëîïôöùûüÿ'):
                return 'fr'
            
            # Проверяем немецкие символы
            if any(german_char in text_lower for german_char in 'äöüß'):
                return 'de'
            
            return None
        
        except:
            return None
