"""
🎤 ПОЛНОЦЕННЫЙ ПЕРЕВОДЧИК С GOOGLE WEB SPEECH API
Использует бесплатный Google Web Speech API через speech_recognition
и requests для перевода
"""

import sys

# PyQt5 для GUI
from PyQt5.QtWidgets import QApplication, QMessageBox

# Для распознавания речи
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False
    print("⚠️ SpeechRecognition не установлен. pip install SpeechRecognition")

# Импорты из новых модулей
from app.ui.main_window import GoogleWebSpeechTranslator


def main():
    """Запуск приложения"""
    app = QApplication(sys.argv)

    if not SPEECH_RECOGNITION_AVAILABLE:
        QMessageBox.critical(None, "Ошибка",
            "SpeechRecognition не установлен!\n\n"
            "Установите:\n"
            "pip install SpeechRecognition")
        return

    # Создаем и показываем окно
    translator = GoogleWebSpeechTranslator()

    # Открываем во весь экран
    translator.showFullScreen()

    # Обновляем текст кнопки
    translator.fullscreen_btn.setText("⛶")

    sys.exit(app.exec_())


if __name__ == "__main__":
    print("=" * 70)
    print("🎤 ПЕРЕВОДЧИК: GOOGLE WEB SPEECH API + ELEVENLABS TTS".center(70))
    print("=" * 70)

    print("\n✅ Используемые технологии:")
    print("  • Google Web Speech API - БЕСПЛАТНОЕ распознавание речи")
    print("  • Google Translate API - БЕСПЛАТНЫЙ перевод текста")
    print("  • ElevenLabs TTS - Качественное озвучивание переводов")
    print("  • SpeechRecognition - библиотека для работы с микрофоном")
    print("  • PyQt5 - графический интерфейс")

    print("\n🚀 Возможности:")
    print("  • Распознавание речи через бесплатный Google Web Speech API")
    print("  • Озвучивание переводов через ElevenLabs TTS (требуется API ключ)")
    print("  • Кнопка 🔊 для озвучивания каждого сообщения")
    print("  • Настройка голоса, громкости и скорости речи")
    print("  • Автоматическое озвучивание новых сообщений")
    print("  • Поддержка 5 языков: RU, EN, ES, FR, DE")

    print("\n⚠️ ВАЖНО для ElevenLabs:")
    print("  • Бесплатный тариф теперь требует использование новых моделей")
    print("  • Используйте eleven_turbo_v2 или eleven_multilingual_v2")
    print("  • Старые модели (v1) больше не работают в бесплатном тарифе")

    print("\n🔑 Требования для ElevenLabs:")
    print("  • API ключ от https://elevenlabs.io/app")
    print("  • Бесплатный тариф включает 10,000 символов в месяц")
    print("  • Для бесплатного тарифа используйте модели turbo_v2 или multilingual_v2")

    print("\n🔧 Установка:")
    print("  pip install SpeechRecognition PyQt5 requests")
    print("=" * 70)

    main()
