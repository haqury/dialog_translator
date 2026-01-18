"""TTS провайдеры"""
from .base_provider import BaseTTSProvider
from .elevenlabs_provider import ElevenLabsProvider
from .google_cloud_provider import GoogleCloudProvider

__all__ = [
    'BaseTTSProvider',
    'ElevenLabsProvider',
    'GoogleCloudProvider',
]
