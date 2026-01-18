"""Конфигурация приложения"""
import json
import os
from pathlib import Path
from typing import Dict, Any

# Путь к файлу конфигурации
CONFIG_FILE = Path(__file__).parent.parent / 'config.json'

# Настройки по умолчанию (объединенные: основные + TTS)
DEFAULT_CONFIG = {
    # Основные настройки
    'language1': 'ru',  # Язык первого говорящего
    'language2': 'en',  # Язык второго говорящего
    'opacity': 0.95,
    'font_size': 11,
    'speaker1_color': '#FF6B6B',
    'speaker2_color': '#4ECDC4',
    'max_messages': 30,
    'sample_rate': 16000,
    'record_duration': 300,
    'energy_threshold': 300,
    'pause_threshold': 0.8,
    'selected_mic_index': 0,
    'translation_timeout': 5,
    'auto_detect_language': True,
    'listen_timeout': 10,
    'phrase_time_limit': 10,
    'enable_text_input': False,
    # Настройки ElevenLabs TTS
    'enable_tts': True,
    'tts_provider': 'elevenlabs',
    'tts_voice_id': 'CwhRBWXzGAHq8TQ4Fs17',  # Roger по умолчанию
    'tts_volume': 80,
    'tts_speed': 1.0,
    'elevenlabs_api_key': '',  # Пользователь должен ввести свой ключ (секрет)
    'auto_play_tts': False,
    # Новые настройки для совместимости с бесплатным тарифом
    'tts_model': 'eleven_turbo_v2',  # Новая модель для бесплатного тарифа
}

# Поля, которые считаются секретами (не логируются)
SECRET_FIELDS = {'elevenlabs_api_key'}


def load_config() -> Dict[str, Any]:
    """
    Загружает конфигурацию из файла или возвращает настройки по умолчанию
    
    Returns:
        Словарь с настройками
    """
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                saved_config = json.load(f)
            
            # Объединяем с настройками по умолчанию (приоритет у сохраненных)
            config = DEFAULT_CONFIG.copy()
            config.update(saved_config)
            
            # Убеждаемся, что все ключи из DEFAULT_CONFIG присутствуют
            for key in DEFAULT_CONFIG:
                if key not in config:
                    config[key] = DEFAULT_CONFIG[key]
            
            # Миграция: заменяем устаревшие модели TTS на новые
            deprecated_models = ['eleven_multilingual_v1', 'eleven_monolingual_v1']
            if config.get('tts_model') in deprecated_models:
                print(f"⚠️ Обнаружена устаревшая модель TTS: {config['tts_model']}")
                print("   Автоматически заменяю на eleven_turbo_v2")
                config['tts_model'] = 'eleven_turbo_v2'
                # Сохраняем обновленный конфиг
                save_config(config)
            
            print(f"✅ Конфигурация загружена из {CONFIG_FILE}")
            return config
        except Exception as e:
            print(f"⚠️ Ошибка загрузки конфигурации: {e}")
            print("Используются настройки по умолчанию")
            return DEFAULT_CONFIG.copy()
    else:
        print("📝 Файл конфигурации не найден, используются настройки по умолчанию")
        return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> bool:
    """
    Сохраняет конфигурацию в файл
    
    Args:
        config: Словарь с настройками
        
    Returns:
        True если сохранение успешно, False в противном случае
    """
    try:
        # Создаем директорию если её нет
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Сохраняем все настройки (включая секреты)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        
        print(f"✅ Конфигурация сохранена в {CONFIG_FILE}")
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения конфигурации: {e}")
        return False


def get_config_for_logging(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Возвращает конфигурацию с замаскированными секретами для логирования
    
    Args:
        config: Словарь с настройками
        
    Returns:
        Копия конфигурации с замаскированными секретами
    """
    masked_config = config.copy()
    for field in SECRET_FIELDS:
        if field in masked_config and masked_config[field]:
            value = masked_config[field]
            if len(value) > 8:
                masked_config[field] = value[:4] + '*' * (len(value) - 8) + value[-4:]
            else:
                masked_config[field] = '*' * len(value)
    return masked_config

# Маппинг языков
LANGUAGE_MAP = {
    '🇷🇺 RU': ('ru', 'ru-RU'),
    '🇺🇸 EN': ('en', 'en-US'),
    '🇪🇸 ES': ('es', 'es-ES'),
    '🇫🇷 FR': ('fr', 'fr-FR'),
    '🇩🇪 DE': ('de', 'de-DE'),
}

# Голоса ElevenLabs по языкам
TTS_VOICES = {
    'ru': 'IKne3meq5aSn9XLyUdCD',  # Default Russian voice
    'en': 'CwhRBWXzGAHq8TQ4Fs17',  # Roger
    'es': 'MF3mGyEYCl7XYWbV9V6O',  # Default Spanish voice
    'fr': 'N2lVS1w4EtoT3dr4eOWO',  # Default French voice
    'de': 'ThT5KcBeYPX3keUQqHPh',  # Default German voice
}
