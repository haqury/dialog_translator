"""Фабрика для создания TTS провайдеров"""
from typing import Optional, Dict, Any
from app.services.tts_providers import (
    ElevenLabsProvider,
    GoogleCloudProvider
)


def create_tts_provider(config: Dict[str, Any], message_callback=None):
    """
    Создает TTS провайдер на основе конфигурации
    
    Args:
        config: Словарь с настройками
        message_callback: Функция для отправки сообщений
        
    Returns:
        Экземпляр провайдера или None
    """
    provider_name = config.get('tts_provider', 'elevenlabs')
    
    if provider_name == 'elevenlabs':
        return ElevenLabsProvider(
            api_key=config.get('elevenlabs_api_key', ''),
            model=config.get('elevenlabs_model', 'eleven_turbo_v2'),
            default_voice_id=config.get('elevenlabs_voice_id', 'CwhRBWXzGAHq8TQ4Fs17'),
            message_callback=message_callback
        )
    
    elif provider_name == 'google_cloud':
        return GoogleCloudProvider(
            api_key=config.get('google_cloud_api_key', ''),
            project_id=config.get('google_cloud_project_id', ''),
            default_voice=config.get('google_cloud_voice_name', 'ru-RU-Standard-A'),
            message_callback=message_callback
        )
    
    return None
