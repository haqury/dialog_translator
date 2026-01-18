"""
🎤 ПОЛНОЦЕННЫЙ ПЕРЕВОДЧИК С GOOGLE WEB SPEECH API
Использует бесплатный Google Web Speech API через speech_recognition
и requests для перевода
"""

import sys
import threading
import queue
import time
import json
import requests
import tempfile
import os
import base64
from datetime import datetime
from typing import Optional, Tuple
import urllib.parse
from pathlib import Path

# PyQt5 для GUI
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QTimer, Qt, QEvent, QUrl, QMetaObject, Q_ARG, pyqtSignal
from PyQt5.QtGui import *
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent, QAudioDeviceInfo, QAudio
from PyQt5.QtMultimediaWidgets import QVideoWidget

# Для распознавания речи
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False
    print("⚠️ SpeechRecognition не установлен. pip install SpeechRecognition")

# Импорты из новых модулей
from app.models.dialogue import DialogueMessage
from app.widgets.chat_widget import ChatWidget
from app.services.translation_service import TranslationService
from app.services.tts_service import TTSService
from app.services.speech_service import SpeechService
from app.config import DEFAULT_CONFIG, LANGUAGE_MAP, TTS_VOICES, load_config, save_config

# ChatWidget теперь импортируется из app.widgets.chat_widget

class GoogleWebSpeechTranslator(QMainWindow):
    # Сигнал для передачи списка голосов из потока в главный поток
    voices_loaded = pyqtSignal(list)
    
    def __init__(self):
        super().__init__()
        
        # Подключаем сигнал
        def on_voices_loaded(voices):
            print(f"🔊 DEBUG: Сигнал voices_loaded получен с {len(voices) if voices else 0} голосами")
            self.show_voice_selection_dialog(voices)
        
        self.voices_loaded.connect(on_voices_loaded)

        # Загружаем настройки из файла или используем по умолчанию
        self.config = load_config()

        # Инициализация компонентов
        self.recognizer = None
        self.microphone = None
        self.available_mics = []
        self.init_components()

        # История диалога
        self.dialogue_history = []
        self.speaker_stats = {'Speaker 1': 0, 'Speaker 2': 0}

        # Очереди
        self.message_queue = queue.Queue()

        # Потоки
        self.is_recording = False
        self.recording_thread = None
        self.should_stop_recording = threading.Event()

        # Статистика аудио
        self.audio_stats = {
            'current_volume': 0,
            'recording_start': None,
            'is_listening': False
        }

        # Для TTS (Text-to-Speech)
        self.tts_player = QMediaPlayer()
        self.tts_player.mediaStatusChanged.connect(self.handle_media_status)
        self.current_tts_file = None
        self.is_playing_tts = False

        # Инициализация UI
        self.init_ui()

    def init_components(self):
        """Инициализация компонентов распознавания"""
        if SPEECH_RECOGNITION_AVAILABLE:
            try:
                self.recognizer = sr.Recognizer()
                self.recognizer.energy_threshold = self.config['energy_threshold']
                self.recognizer.dynamic_energy_threshold = True
                self.recognizer.pause_threshold = self.config['pause_threshold']

                # Получаем список микрофонов
                print("🔍 Поиск микрофонов...")
                self.available_mics = sr.Microphone.list_microphone_names()
                if self.available_mics:
                    print(f"✅ Найдено микрофонов: {len(self.available_mics)}")
                    for i, mic in enumerate(self.available_mics[:3]):
                        print(f"  {i}: {mic}")

                    try:
                        self.microphone = sr.Microphone(
                            device_index=self.config['selected_mic_index'],
                            sample_rate=self.config['sample_rate']
                        )
                        print(f"✅ Выбран микрофон: {self.available_mics[self.config['selected_mic_index']]}")
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

    def init_ui(self):
        """Инициализация интерфейса"""
        self.setWindowTitle("🎤 Переводчик с Google Web Speech API + ElevenLabs TTS")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # ===== КОМПАКТНЫЙ HEADER С ВСЕМИ ЭЛЕМЕНТАМИ =====
        header_panel = self.create_header_panel()
        layout.addLayout(header_panel)

        # ===== АУДИО ИНДИКАТОРЫ =====
        audio_panel = self.create_audio_panel()
        layout.addLayout(audio_panel)

        # ===== ЧАТ =====
        self.chat_widget = ChatWidget()
        self.chat_widget.setMinimumHeight(350)
        layout.addWidget(self.chat_widget)

        # ===== ПАНЕЛЬ РУЧНОГО ВВОДА (если включена) =====
        self.input_panel = self.create_input_panel()
        layout.addLayout(self.input_panel)

        # Применяем стили
        self.apply_styles()

        # Устанавливаем прозрачность
        self.setWindowOpacity(self.config['opacity'])

        # Устанавливаем размер по умолчанию
        self.resize(800, 700)

        # Таймер для обновления UI
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self.update_ui)
        self.ui_timer.start(100)

        # Добавляем инструкцию
        self.add_instruction_message()

    def create_header_panel(self):
        """Создает header со всеми элементами управления"""
        layout = QHBoxLayout()
        layout.setSpacing(6)

        layout.addSpacing(10)

        # Заголовок
        title = QLabel("🎤 Переводчик + ElevenLabs TTS")
        title.setObjectName("HeaderTitle")
        title.setFixedHeight(30)
        layout.addWidget(title)

        layout.addSpacing(10)

        # Компактные языки
        lang_layout = QHBoxLayout()
        lang_layout.setSpacing(4)

        # Speaker 1 язык
        self.lang1_combo = QComboBox()
        self.lang1_combo.addItems(['🇷🇺 RU', '🇺🇸 EN', '🇪🇸 ES', '🇫🇷 FR', '🇩🇪 DE'])
        self.lang1_combo.setCurrentText('🇷🇺 RU')
        self.lang1_combo.setFixedWidth(80)

        # Стрелка
        arrow = QLabel("⇄")
        arrow.setObjectName("HeaderArrow")

        # Speaker 2 язык
        self.lang2_combo = QComboBox()
        self.lang2_combo.addItems(['🇺🇸 EN', '🇷🇺 RU', '🇪🇸 ES', '🇫🇷 FR', '🇩🇪 DE'])
        self.lang2_combo.setCurrentText('🇺🇸 EN')
        self.lang2_combo.setFixedWidth(80)

        lang_layout.addWidget(self.lang1_combo)
        lang_layout.addWidget(arrow)
        lang_layout.addWidget(self.lang2_combo)
        layout.addLayout(lang_layout)

        layout.addSpacing(10)

        # Выбор микрофона
        self.mic_combo = QComboBox()
        if self.available_mics:
            for i, mic_name in enumerate(self.available_mics):
                short_name = mic_name[:15] if len(mic_name) > 15 else mic_name
                self.mic_combo.addItem(f"🎤 {short_name}", i)
            self.mic_combo.setFixedWidth(120)
            # Исправляем шрифты для ComboBox
            self.mic_combo.setStyleSheet("""
                QComboBox {
                    font-family: "Segoe UI", Arial, sans-serif;
                    font-size: 11px;
                }
                QComboBox QAbstractItemView {
                    font-family: "Segoe UI", Arial, sans-serif;
                    font-size: 11px;
                }
            """)
        else:
            self.mic_combo.addItem("🎤 Нет", -1)
            self.mic_combo.setEnabled(False)
            self.mic_combo.setFixedWidth(80)

        layout.addWidget(self.mic_combo)
        
        # Выбор устройства воспроизведения
        self.output_combo = QComboBox()
        try:
            # В PyQt5 используем QAudio.AudioOutput для получения устройств вывода
            all_devices = QAudioDeviceInfo.availableDevices(QAudio.AudioOutput)
            if all_devices:
                self.output_combo.addItem("🔊 По умолчанию", "")
                for device in all_devices:
                    device_name = device.deviceName()
                    short_name = device_name[:15] if len(device_name) > 15 else device_name
                    self.output_combo.addItem(f"🔊 {short_name}", device_name)
                # Восстанавливаем сохраненное устройство
                saved_output = self.config.get('selected_output_device', '')
                if saved_output:
                    index = self.output_combo.findData(saved_output)
                    if index >= 0:
                        self.output_combo.setCurrentIndex(index)
                self.output_combo.setFixedWidth(120)
                # Исправляем шрифты для ComboBox
                self.output_combo.setStyleSheet("""
                    QComboBox {
                        font-family: "Segoe UI", Arial, sans-serif;
                        font-size: 11px;
                    }
                    QComboBox QAbstractItemView {
                        font-family: "Segoe UI", Arial, sans-serif;
                        font-size: 11px;
                    }
                """)
                self.output_combo.currentIndexChanged.connect(self.on_output_device_changed)
            else:
                self.output_combo.addItem("🔊 Нет", "")
                self.output_combo.setEnabled(False)
                self.output_combo.setFixedWidth(80)
        except (AttributeError, ImportError) as e:
            # Если не удалось получить устройства, просто показываем "По умолчанию"
            print(f"⚠️ Не удалось получить список устройств вывода: {e}")
            self.output_combo.addItem("🔊 По умолчанию", "")
            self.output_combo.setFixedWidth(120)
            self.output_combo.setStyleSheet("""
                QComboBox {
                    font-family: "Segoe UI", Arial, sans-serif;
                    font-size: 11px;
                }
                QComboBox QAbstractItemView {
                    font-family: "Segoe UI", Arial, sans-serif;
                    font-size: 11px;
                }
            """)
            self.output_combo.currentIndexChanged.connect(self.on_output_device_changed)
        
        layout.addWidget(self.output_combo)

        layout.addStretch()

        # Основная кнопка записи
        self.record_btn = QPushButton("🎤 НАЧАТЬ")
        self.record_btn.clicked.connect(self.toggle_recording)
        self.record_btn.setEnabled(self.recognizer is not None and self.microphone is not None)
        self.record_btn.setFixedHeight(30)
        self.record_btn.setFixedWidth(100)

        # Кнопки управления (компактные)
        button_style = """
            QPushButton {
                background-color: rgba(40, 45, 55, 180);
                color: white;
                border: 1px solid rgba(60, 65, 75, 180);
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 11px;
                min-width: 40px;
            }
            QPushButton:hover {
                background-color: rgba(50, 55, 65, 180);
            }
            QPushButton:pressed {
                background-color: rgba(30, 35, 45, 180);
            }
        """

        self.clear_btn = QPushButton("🗑️")
        self.clear_btn.clicked.connect(self.clear_dialog)
        self.clear_btn.setStyleSheet(button_style)
        self.clear_btn.setFixedSize(32, 30)
        self.clear_btn.setToolTip("Очистить чат")

        self.export_btn = QPushButton("💾")
        self.export_btn.clicked.connect(self.export_dialog)
        self.export_btn.setStyleSheet(button_style)
        self.export_btn.setFixedSize(32, 30)
        self.export_btn.setToolTip("Экспорт чата")

        self.settings_btn = QPushButton("⚙️")
        self.settings_btn.clicked.connect(self.show_settings)
        self.settings_btn.setStyleSheet(button_style)
        self.settings_btn.setFixedSize(32, 30)
        self.settings_btn.setToolTip("Настройки (все параметры)")

        # Добавляем кнопки управления
        layout.addWidget(self.clear_btn)
        layout.addWidget(self.export_btn)
        layout.addWidget(self.settings_btn)
        layout.addSpacing(10)
        layout.addWidget(self.record_btn)
        
        layout.addStretch()
        
        # Кнопка разворачивания на весь экран (справа)
        self.fullscreen_btn = QPushButton("⛶")
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        self.fullscreen_btn.setFixedSize(28, 28)
        self.fullscreen_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(60, 120, 200, 180);
                color: white;
                border: none;
                border-radius: 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(80, 140, 220, 220);
            }
            QPushButton:pressed {
                background-color: rgba(40, 100, 180, 220);
            }
        """)
        layout.addWidget(self.fullscreen_btn)
        
        # КНОПКА ЗАКРЫТИЯ (справа)
        self.close_btn = QPushButton("✕")
        self.close_btn.clicked.connect(self.close)
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(200, 60, 60, 180);
                color: white;
                border: none;
                border-radius: 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(220, 80, 80, 220);
            }
            QPushButton:pressed {
                background-color: rgba(180, 40, 40, 220);
            }
        """)
        layout.addWidget(self.close_btn)

        return layout

    def create_audio_panel(self):
        """Создает панель аудио индикаторов"""
        layout = QVBoxLayout()
        layout.setSpacing(4)

        # Индикатор уровня громкости
        self.volume_meter = QProgressBar()
        self.volume_meter.setRange(0, 100)
        self.volume_meter.setValue(0)
        self.volume_meter.setTextVisible(False)
        self.volume_meter.setFixedHeight(4)

        # Компактная строка статусов
        status_layout = QHBoxLayout()

        self.listening_status = QLabel("🔴 Выкл.")
        self.listening_status.setStyleSheet("font-size: 11px;")

        self.recognition_status = QLabel("Готов")
        self.recognition_status.setStyleSheet("font-size: 11px; color: #888888;")

        self.recording_time = QLabel("00:00")
        self.recording_time.setStyleSheet("font-size: 11px; color: #666666; font-family: monospace;")

        status_layout.addWidget(self.listening_status)
        status_layout.addStretch()
        status_layout.addWidget(self.recognition_status)
        status_layout.addStretch()
        status_layout.addWidget(self.recording_time)

        layout.addWidget(self.volume_meter)
        layout.addLayout(status_layout)

        return layout

    def create_input_panel(self):
        """Создает панель ручного ввода (скрыта по умолчанию)"""
        layout = QHBoxLayout()
        layout.setSpacing(6)

        self.manual_input = QLineEdit()
        self.manual_input.setPlaceholderText("Ручной ввод текста...")
        self.manual_input.returnPressed.connect(self.process_manual_input)
        self.manual_input.setVisible(self.config['enable_text_input'])

        self.send_btn = QPushButton("📤")
        self.send_btn.clicked.connect(self.process_manual_input)
        self.send_btn.setFixedWidth(40)
        self.send_btn.setFixedHeight(30)
        self.send_btn.setVisible(self.config['enable_text_input'])

        layout.addWidget(self.manual_input)
        layout.addWidget(self.send_btn)

        return layout

    def apply_styles(self):
        """Применяет стили"""
        style = """
        QMainWindow {
            background-color: rgba(20, 25, 35, 230);
            border-radius: 12px;
            border: 2px solid rgba(40, 45, 55, 200);
        }
        
        QWidget#CentralWidget {
            background-color: rgba(25, 30, 40, 220);
            border-radius: 10px;
        }
        
        QLabel {
            color: #FFFFFF;
        }
        
        QLabel#HeaderTitle {
            color: #FFFFFF;
            font-size: 14px;
            font-weight: bold;
            padding: 0px 8px;
        }
        
        QLabel#HeaderArrow {
            color: #4ECDC4;
            font-size: 16px;
            font-weight: bold;
        }
        
        QScrollArea {
            background-color: transparent;
            border: 1px solid rgba(40, 45, 55, 200);
            border-radius: 8px;
        }
        
        QScrollBar:vertical {
            background-color: rgba(40, 45, 55, 180);
            width: 8px;
            border-radius: 4px;
        }
        
        QScrollBar::handle:vertical {
            background-color: rgba(78, 205, 196, 0.5);
            border-radius: 4px;
            min-height: 20px;
        }
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        
        QPushButton {
            background-color: rgba(40, 45, 55, 200);
            color: white;
            border: 1px solid rgba(60, 65, 75, 200);
            border-radius: 6px;
            padding: 6px 12px;
            font-weight: bold;
            font-size: 12px;
        }
        
        QPushButton:hover {
            background-color: rgba(50, 55, 65, 200);
        }
        
        QPushButton:pressed {
            background-color: rgba(30, 35, 45, 200);
        }
        
        QPushButton:disabled {
            background-color: rgba(30, 35, 45, 150);
            color: #666666;
        }
        
        QLineEdit {
            background-color: rgba(35, 40, 50, 180);
            color: white;
            border: 1px solid rgba(60, 65, 75, 180);
            border-radius: 4px;
            padding: 6px 10px;
            font-size: 12px;
        }
        
        QLineEdit:focus {
            border: 1px solid #4ECDC4;
        }
        
        QProgressBar {
            background-color: rgba(30, 35, 45, 180);
            border: none;
            border-radius: 2px;
        }
        
        QProgressBar::chunk {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #4ECDC4, stop:0.5 #45B7D1, stop:1 #2E86AB);
            border-radius: 2px;
        }
        
        QComboBox {
            background-color: rgba(40, 45, 55, 180);
            color: white;
            border: 1px solid rgba(60, 65, 75, 180);
            border-radius: 4px;
            padding: 4px 6px;
            font-size: 11px;
        }
        
        QComboBox::drop-down {
            border: none;
        }
        
        QComboBox QAbstractItemView {
            background-color: rgba(40, 45, 55, 220);
            color: white;
            selection-background-color: #4ECDC4;
            border: 1px solid rgba(60, 65, 75, 180);
        }
        """

        self.setStyleSheet(style)

    def speak_text(self, text, source_lang="en"):
        """Озвучивает текст через ElevenLabs"""
        if not self.config['enable_tts'] or not text.strip():
            return

        if not self.config['elevenlabs_api_key']:
            self.message_queue.put(('error', "❌ ElevenLabs API ключ не установлен"))
            return

        # Определяем голос в зависимости от языка
        voice_id = self.config['tts_voice_id']
        if source_lang == 'ru':
            # Для русского можно использовать другой голос
            voice_id = 'IKne3meq5aSn9XLyUdCD'  # Default Russian voice
        elif source_lang == 'es':
            voice_id = 'MF3mGyEYCl7XYWbV9V6O'  # Default Spanish voice
        elif source_lang == 'fr':
            voice_id = 'N2lVS1w4EtoT3dr4eOWO'  # Default French voice
        elif source_lang == 'de':
            voice_id = 'ThT5KcBeYPX3keUQqHPh'  # Default German voice

        # Запускаем в отдельном потоке
        threading.Thread(target=self.elevenlabs_tts_worker,
                        args=(text, voice_id),
                        daemon=True).start()

    def elevenlabs_tts_worker(self, text, voice_id):
        """Поток для работы с ElevenLabs API"""
        try:
            self.message_queue.put(('status', "🔊 Озвучивание..."))

            # Подробная отладка
            print(f"\n" + "=" * 60)
            print(f"🔊 DEBUG: Запуск ElevenLabs TTS")
            print(f"🔊 DEBUG: Текст: '{text[:50]}...'")
            print(f"🔊 DEBUG: Voice ID: {voice_id}")
            print(f"🔊 DEBUG: Ключ: {self.config['elevenlabs_api_key'][:10]}...")
            print("=" * 60)

            # Проверяем наличие ключа
            api_key = self.config['elevenlabs_api_key'].strip()
            if not api_key:
                error_msg = "❌ API ключ ElevenLabs не установлен"
                print(f"❌ DEBUG: {error_msg}")
                self.message_queue.put(('error', error_msg))
                return

            # Проверяем формат ключа
            if not api_key.startswith("sk_"):
                error_msg = "❌ Неверный формат ключа (должен начинаться с 'sk_')"
                print(f"❌ DEBUG: {error_msg}")
                self.message_queue.put(('error', error_msg))
                return

            # Подготовка данных для запроса
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": api_key
            }

            # Используем новую модель для бесплатного тарифа
            # Автоматическая миграция устаревших моделей
            tts_model = self.config['tts_model']
            deprecated_models = ['eleven_multilingual_v1', 'eleven_monolingual_v1']
            if tts_model in deprecated_models:
                print(f"⚠️ Обнаружена устаревшая модель TTS: {tts_model}")
                print("   Автоматически заменяю на eleven_turbo_v2")
                tts_model = 'eleven_turbo_v2'
                self.config['tts_model'] = tts_model
                save_config(self.config)  # Сохраняем обновленную модель
            
            data = {
                "text": text,
                "model_id": tts_model,  # Используем настройку модели
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.5,
                    "speed": self.config['tts_speed'],
                    "use_speaker_boost": True
                }
            }

            print(f"🔊 DEBUG: Отправляю запрос на {url}")
            print(f"🔊 DEBUG: Заголовки: {headers}")
            print(f"🔊 DEBUG: Данные: {data}")

            # Выполняем запрос с таймаутом
            import time
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
                self.message_queue.put(('error', error_msg))
                return

            except requests.exceptions.RequestException as e:
                error_msg = f"❌ Ошибка сети: {str(e)[:50]}"
                print(f"❌ DEBUG: {error_msg}")
                self.message_queue.put(('error', error_msg))
                return

            if response.status_code == 200:
                if response.content:
                    # Сохраняем аудио во временный файл
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                        f.write(response.content)
                        temp_file = f.name

                    print(f"🔊 DEBUG: Аудио сохранено в {temp_file}")
                    print(f"🔊 DEBUG: Размер файла: {len(response.content)} байт")

                    # Воспроизводим через Qt Media Player
                    self.play_audio_file(temp_file)
                    self.message_queue.put(('info', "✅ Озвучивание успешно"))
                else:
                    error_msg = "❌ Пустой ответ от сервера"
                    print(f"❌ DEBUG: {error_msg}")
                    self.message_queue.put(('error', error_msg))

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
                self.message_queue.put(('error', error_msg))

            elif response.status_code == 402:
                error_msg = "❌ Закончились бесплатные символы"
                print(f"❌ DEBUG: {error_msg}")
                self.message_queue.put(('error', error_msg))

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
                self.message_queue.put(('error', error_msg))

            elif response.status_code == 429:
                error_msg = "❌ Слишком много запросов. Попробуйте позже"
                print(f"❌ DEBUG: {error_msg}")
                self.message_queue.put(('error', error_msg))

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
                self.message_queue.put(('error', error_msg))

            print(f"🔊 DEBUG: Конец TTS запроса")
            print("=" * 60 + "\n")

        except Exception as e:
            import traceback
            print(f"❌ DEBUG: Неожиданная ошибка: {e}")
            print(f"❌ DEBUG: Traceback: {traceback.format_exc()}")
            self.message_queue.put(('error', f"❌ Ошибка озвучивания: {str(e)[:50]}"))

    def play_audio_file(self, file_path):
        """Воспроизводит аудио файл"""
        try:
            # Останавливаем предыдущее воспроизведение
            if self.tts_player.state() == QMediaPlayer.PlayingState:
                self.tts_player.stop()

            # Удаляем предыдущий временный файл
            if self.current_tts_file and os.path.exists(self.current_tts_file):
                try:
                    os.unlink(self.current_tts_file)
                except:
                    pass

            # Сохраняем ссылку на текущий файл
            self.current_tts_file = file_path

            # Устанавливаем громкость
            volume = self.config['tts_volume']
            self.tts_player.setVolume(volume)

            # Воспроизводим
            self.tts_player.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))
            self.tts_player.play()

            self.is_playing_tts = True
            self.message_queue.put(('info', "🔊 Воспроизведение..."))

        except Exception as e:
            print(f"❌ Ошибка воспроизведения: {e}")

    def on_output_device_changed(self, index):
        """Обрабатывает изменение устройства воспроизведения"""
        device_name = self.output_combo.itemData(index)
        if device_name is not None:
            self.config['selected_output_device'] = device_name
            save_config(self.config)
            print(f"✅ Устройство воспроизведения изменено: {device_name if device_name else 'По умолчанию'}")

    def handle_media_status(self, status):
        """Обрабатывает статус медиаплеера"""
        if status == QMediaPlayer.EndOfMedia:
            self.is_playing_tts = False
            # Удаляем временный файл
            if self.current_tts_file and os.path.exists(self.current_tts_file):
                try:
                    os.unlink(self.current_tts_file)
                    self.current_tts_file = None
                except:
                    pass
        elif status == QMediaPlayer.InvalidMedia:
            self.message_queue.put(('error', "❌ Ошибка воспроизведения аудио"))

    # Старый метод show_tts_settings() удален - теперь все настройки в show_settings()

    def update_tts_model(self, index):
        """Обновляет выбранную модель TTS"""
        models = {
            0: 'eleven_turbo_v2',
            1: 'eleven_multilingual_v2',
            2: 'eleven_multilingual_v1'  # Deprecated
        }
        model = models.get(index, 'eleven_turbo_v2')
        self.config['tts_model'] = model
        save_config(self.config)  # Сохраняем конфиг
        print(f"DEBUG: Выбрана модель: {model}")

    def show_tts_error(self, message):
        """Показывает ошибку внутри диалога настроек"""
        self.tts_error_message = message
        self.error_label.setText(message)
        self.error_widget.setVisible(True)

    def hide_tts_error(self):
        """Скрывает ошибку внутри диалога настроек"""
        self.tts_error_message = ""
        self.error_widget.setVisible(False)

    def test_tts_from_dialog(self, dialog):
        """Тестирует TTS из диалога настроек"""
        # Получаем API ключ из поля ввода
        api_key = self.api_key_input.text().strip()

        if not api_key:
            self.show_tts_error("❌ API ключ не установлен. Введите ключ ElevenLabs.")
            return

        if not api_key.startswith("sk_"):
            self.show_tts_error("❌ Неверный формат ключа. Ключ должен начинаться с 'sk_'")
            return

        # Сохраняем ключ в конфиг для теста
        self.config['elevenlabs_api_key'] = api_key
        save_config(self.config)  # Сохраняем конфиг (включая секрет)

        # Проверяем модель
        model = self.config.get('tts_model', 'eleven_turbo_v2')
        if model in ['eleven_multilingual_v1', 'eleven_monolingual_v1']:
            self.show_tts_error("⚠️ Выбрана устаревшая модель. Используйте eleven_turbo_v2 или eleven_multilingual_v2 для бесплатного тарифа.")
            return

        # Меняем текст кнопки
        self.test_btn.setText("⏳...")
        self.test_btn.setEnabled(False)
        self.tts_test_in_progress = True

        # Тестовое сообщение
        test_text = "Привет! Это тестовое сообщение для проверки озвучивания через ElevenLabs."

        # Запускаем тест в отдельном потоке
        threading.Thread(target=self.test_tts_worker,
                        args=(test_text, dialog),
                        daemon=True).start()

    def test_tts_worker(self, text, dialog):
        """Рабочий поток для тестирования TTS"""
        try:
            # Используем голос из настроек
            # Получаем voice_id из комбобокса
            current_index = self.voice_combo.currentIndex()
            if current_index >= 0:
                voice_id = self.voice_combo.itemData(current_index)
                if not voice_id:
                    voice_id = self.voice_combo.currentText().strip()
            else:
                voice_id = self.voice_combo.currentText().strip()
            if not voice_id:
                voice_id = self.config['tts_voice_id']

            # Делаем запрос к API
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.config['elevenlabs_api_key']
            }

            data = {
                "text": text,
                "model_id": self.config.get('tts_model', 'eleven_turbo_v2'),
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.5,
                    "speed": self.config['tts_speed'],
                    "use_speaker_boost": True
                }
            }

            response = requests.post(url, json=data, headers=headers, timeout=30)

            if response.status_code == 200:
                # Сохраняем и воспроизводим
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                    f.write(response.content)
                    temp_file = f.name

                # Воспроизводим через Qt
                def play_audio():
                    try:
                        self.tts_player.setMedia(QMediaContent(QUrl.fromLocalFile(temp_file)))
                        self.tts_player.setVolume(self.config['tts_volume'])
                        self.tts_player.play()

                        # Обновляем UI в основном потоке
                        dialog.findChild(QPushButton, "test_btn").setText("🔊 Тест")
                        dialog.findChild(QPushButton, "test_btn").setEnabled(True)
                        self.hide_tts_error()

                        # Удаляем файл после воспроизведения
                        QTimer.singleShot(5000, lambda: os.unlink(temp_file) if os.path.exists(temp_file) else None)

                    except Exception as e:
                        print(f"Ошибка воспроизведения: {e}")
                        dialog.findChild(QPushButton, "test_btn").setText("🔊 Тест")
                        dialog.findChild(QPushButton, "test_btn").setEnabled(True)
                        self.show_tts_error(f"❌ Ошибка воспроизведения: {str(e)[:50]}")

                # Запускаем в основном потоке
                QMetaObject.invokeMethod(dialog, "play_audio", Qt.QueuedConnection)

            elif response.status_code == 401:
                error_data = response.json()
                if 'detail' in error_data:
                    detail = error_data['detail']
                    if isinstance(detail, dict) and 'message' in detail:
                        error_msg = detail['message']
                    else:
                        error_msg = str(detail)
                else:
                    error_msg = "Неверный API ключ"

                self.show_tts_error(f"❌ {error_msg}")
                dialog.findChild(QPushButton, "test_btn").setText("🔊 Тест")
                dialog.findChild(QPushButton, "test_btn").setEnabled(True)

            elif response.status_code == 422:
                error_data = response.json()
                error_msg = "Ошибка валидации"
                if 'detail' in error_data:
                    error_msg = str(error_data['detail'])[:100]
                self.show_tts_error(f"❌ {error_msg}")
                dialog.findChild(QPushButton, "test_btn").setText("🔊 Тест")
                dialog.findChild(QPushButton, "test_btn").setEnabled(True)

            else:
                self.show_tts_error(f"❌ Ошибка {response.status_code}")
                dialog.findChild(QPushButton, "test_btn").setText("🔊 Тест")
                dialog.findChild(QPushButton, "test_btn").setEnabled(True)

        except requests.exceptions.Timeout:
            self.show_tts_error("❌ Таймаут запроса (30 сек)")
            dialog.findChild(QPushButton, "test_btn").setText("🔊 Тест")
            dialog.findChild(QPushButton, "test_btn").setEnabled(True)

        except Exception as e:
            self.show_tts_error(f"❌ Ошибка: {str(e)[:50]}")
            dialog.findChild(QPushButton, "test_btn").setText("🔊 Тест")
            dialog.findChild(QPushButton, "test_btn").setEnabled(True)

    def show_tts_help(self):
        """Показывает справку по настройкам ElevenLabs"""
        help_text = """<h3>🔊 Помощь по ElevenLabs TTS</h3>

<b>🔑 Получение API ключа:</b><br>
1. Зарегистрируйтесь на <a href="https://elevenlabs.io">elevenlabs.io</a><br>
2. Перейдите в раздел Profile → API Key<br>
3. Скопируйте ваш ключ (начинается с sk_...)<br><br>

<b>🚨 ВАЖНО для бесплатного тарифа:</b><br>
• Старые модели (eleven_multilingual_v1, eleven_monolingual_v1) больше НЕ работают в бесплатном тарифе<br>
• Используйте новые модели:<br>
&nbsp;&nbsp;• <b>eleven_turbo_v2</b> - быстрая, поддерживает множество языков<br>
&nbsp;&nbsp;• <b>eleven_multilingual_v2</b> - улучшенная мультиязычная модель<br><br>

<b>🎤 ID голосов (примеры):</b><br>
• <b>21m00Tcm4TlvDq8ikWAM</b> - Rachel (английский, женский)<br>
• <b>IKne3meq5aSn9XLyUdCD</b> - Default (русский)<br>
• <b>MF3mGyEYCl7XYWbV9V6O</b> - Default (испанский)<br>
• <b>N2lVS1w4EtoT3dr4eOWO</b> - Default (французский)<br><br>

<b>⚡ Бесплатный тариф:</b><br>
• 10,000 символов в месяц<br>
• Только новые модели (turbo_v2, multilingual_v2)<br>
• Для тестирования достаточно<br><br>

<b>🔊 Тестирование:</b><br>
• Нажмите "Тест" чтобы проверить работу<br>
• Должно прозвучать тестовое сообщение<br>
• Ошибки будут показаны вверху окна настроек"""

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Помощь - ElevenLabs TTS")
        msg_box.setText(help_text)
        msg_box.setTextFormat(Qt.RichText)
        msg_box.setIcon(QMessageBox.Information)

        # Делаем окно шире для читаемости
        msg_box.setMinimumWidth(450)

        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()

    def update_tts_setting(self, key, value):
        """Обновляет настройку TTS"""
        self.config[key] = value
        # Если отключаем TTS, останавливаем воспроизведение
        if key == 'enable_tts' and not value:
            if self.tts_player.state() == QMediaPlayer.PlayingState:
                self.tts_player.stop()
        # Автоматически сохраняем конфиг при изменении настроек TTS
        save_config(self.config)

    def save_tts_settings(self, dialog):
        """УСТАРЕЛО: Используйте save_all_settings()"""
        self.save_all_settings(dialog)

    def test_tts(self):
        """Тестирует озвучивание"""
        # Проверяем наличие ключа
        api_key = self.config['elevenlabs_api_key'].strip()

        if not api_key:
            self.message_queue.put(('error', "❌ API ключ не установлен"))
            QMessageBox.warning(self, "Ошибка", "API ключ ElevenLabs не установлен.\n\nВведите ключ в настройках.")
            return

        # Проверяем формат ключа
        if not api_key.startswith("sk_"):
            self.message_queue.put(('error', "❌ Неверный формат ключа (должен начинаться с 'sk_')"))
            QMessageBox.warning(self, "Ошибка", "Неверный формат API ключа.\n\nКлюч должен начинаться с 'sk_'")
            return

        # Проверяем модель
        model = self.config.get('tts_model', 'eleven_turbo_v2')
        if model in ['eleven_multilingual_v1', 'eleven_monolingual_v1']:
            self.message_queue.put(('error', "⚠️ Используется устаревшая модель. Пожалуйста, перейдите в настройки TTS и выберите eleven_turbo_v2 или eleven_multilingual_v2"))
            QMessageBox.warning(self, "Ошибка модели",
                "Используется устаревшая модель, не поддерживаемая бесплатным тарифом.\n\n"
                "Пожалуйста:\n"
                "1. Нажмите кнопку '⚙️' для открытия настроек\n"
                "2. В разделе 'Озвучивание' выберите 'eleven_turbo_v2' или 'eleven_multilingual_v2'\n"
                "3. Нажмите 'Тест' для проверки")
            return

        # Тестовое сообщение на русском
        test_text = "Привет! Это тестовое сообщение для проверки озвучивания через ElevenLabs."

        # Показываем информацию о тесте
        self.message_queue.put(('info', "🔊 Тестирование озвучивания..."))

        # Запускаем тестовое озвучивание
        self.speak_text(test_text, 'ru')

    def toggle_fullscreen(self):
        """Переключает режим полного экрана"""
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_btn.setText("⛶")
            # Возвращаем скругленные углы
            self.setStyleSheet(self.styleSheet() + """
                QMainWindow {
                    border-radius: 12px;
                }
            """)
        else:
            self.showFullScreen()
            self.fullscreen_btn.setText("⛶")
            # Убираем скругленные углы в полноэкранном режиме
            self.setStyleSheet(self.styleSheet() + """
                QMainWindow {
                    border-radius: 0px;
                }
            """)

    def toggle_recording(self):
        """Включение/выключение записи"""
        if not self.recognizer or not self.microphone:
            QMessageBox.warning(self, "Ошибка",
                "Распознавание речи не настроено!\n"
                "Проверьте микрофон и установите SpeechRecognition.")
            return

        self.is_recording = not self.is_recording

        if self.is_recording:
            # Начинаем запись
            self.record_btn.setText("⏹️ СТОП")
            self.record_btn.setStyleSheet("background-color: #D32F2F;")
            self.recognition_status.setText("🎤 Слушаю...")
            self.listening_status.setText("🟢 Вкл.")
            self.listening_status.setStyleSheet("color: #4ECDC4; font-weight: bold; font-size: 11px;")
            self.recording_time.setText("00:00")

            # Сбрасываем флаг остановки
            self.should_stop_recording.clear()

            # Сбрасываем статистику
            self.audio_stats['recording_start'] = time.time()
            self.audio_stats['is_listening'] = True

            # Запускаем поток записи
            self.start_recording_thread()

        else:
            # Останавливаем запись
            self.record_btn.setText("🎤 НАЧАТЬ")
            self.record_btn.setStyleSheet("")
            self.recognition_status.setText("Готов")
            self.listening_status.setText("🔴 Выкл.")
            self.listening_status.setStyleSheet("color: #888888; font-size: 11px;")

            # Устанавливаем флаг остановки
            self.should_stop_recording.set()
            self.stop_recording_thread()

    def start_recording_thread(self):
        """Запускает поток записи аудио"""
        if self.recording_thread and self.recording_thread.is_alive():
            self.should_stop_recording.set()
            self.recording_thread.join(timeout=1)

        self.should_stop_recording.clear()
        self.recording_thread = threading.Thread(target=self.recording_worker, daemon=True)
        self.recording_thread.start()

    def recording_worker(self):
        """Поток для записи и распознавания аудио"""
        print("🎤 Начало работы потока записи...")

        try:
            with self.microphone as source:
                # Настраиваем параметры шумоподавления
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                print("✅ Микрофон откалиброван")

                start_time = time.time()
                consecutive_errors = 0
                max_consecutive_errors = 5

                while self.is_recording and not self.should_stop_recording.is_set():
                    try:
                        # Обновляем время записи
                        elapsed = time.time() - start_time
                        mins = int(elapsed // 60)
                        secs = int(elapsed % 60)
                        self.message_queue.put(('time', f"{mins:02d}:{secs:02d}"))

                        # Слушаем микрофон с таймаутом
                        self.audio_stats['is_listening'] = True
                        self.message_queue.put(('status', "👂 Слушаю..."))

                        # Записываем аудио
                        try:
                            audio = self.recognizer.listen(
                                source,
                                timeout=self.config['listen_timeout'],
                                phrase_time_limit=self.config['phrase_time_limit']
                            )
                        except Exception as e:
                            print(f"⚠️ Ошибка захвата аудио: {e}")
                            time.sleep(0.5)
                            continue

                        # Сбрасываем счетчик ошибок
                        consecutive_errors = 0

                        # Отправляем на распознавание
                        self.message_queue.put(('status', "🔍 Распознавание..."))
                        self.recognize_audio(audio)

                        # Проверяем максимальное время записи
                        if elapsed > self.config['record_duration']:
                            self.message_queue.put(('info', "Максимальное время записи достигнуто"))
                            self.is_recording = False
                            break

                    except sr.WaitTimeoutError:
                        # Таймаут - продолжаем слушать
                        consecutive_errors = 0
                        continue
                    except sr.UnknownValueError:
                        self.message_queue.put(('error', "🗣️ Речь не распознана"))
                        consecutive_errors += 1
                    except sr.RequestError as e:
                        self.message_queue.put(('error', f"❌ Ошибка API: {str(e)[:50]}"))
                        consecutive_errors += 1
                        time.sleep(1)
                    except Exception as e:
                        print(f"❌ Ошибка в потоке записи: {e}")
                        self.message_queue.put(('error', f"Ошибка: {str(e)[:30]}"))
                        consecutive_errors += 1

                    # Если много ошибок подряд, делаем паузу
                    if consecutive_errors >= max_consecutive_errors:
                        print(f"⚠️ Много ошибок подряд ({consecutive_errors}), пауза...")
                        self.message_queue.put(('error', "⚠️ Много ошибок, перезапуск..."))
                        time.sleep(2)
                        consecutive_errors = 0

        except Exception as e:
            print(f"❌ Критическая ошибка записи: {e}")
            self.message_queue.put(('error', f"Критическая ошибка: {str(e)[:50]}"))
            self.is_recording = False

        finally:
            self.audio_stats['is_listening'] = False
            print("🎤 Поток записи завершен")

    def get_language_code(self, display_text):
        """Получает код языка из отображаемого текста"""
        lang_map = {
            '🇷🇺 RU': ('ru', 'ru-RU'),
            '🇺🇸 EN': ('en', 'en-US'),
            '🇪🇸 ES': ('es', 'es-ES'),
            '🇫🇷 FR': ('fr', 'fr-FR'),
            '🇩🇪 DE': ('de', 'de-DE'),
        }
        return lang_map.get(display_text, ('en', 'en-US'))

    def recognize_audio(self, audio):
        """Распознает аудио через Google Web Speech API"""
        try:
            # Получаем языки для распознавания
            lang1_trans, lang1_speech = self.get_language_code(self.lang1_combo.currentText())
            lang2_trans, lang2_speech = self.get_language_code(self.lang2_combo.currentText())

            text = None
            detected_lang = None
            confidence = 0.8

            # Автоопределение языка
            self.message_queue.put(('status', f"🔍 Определяю язык..."))

            # Сначала пробуем автоопределение Google
            try:
                text = self.recognizer.recognize_google(audio, show_all=False)
                if text:
                    # Пытаемся определить язык текста
                    detected_lang = self.detect_language_from_text(text)
                    if not detected_lang:
                        # Если не удалось определить, используем первый язык
                        detected_lang = lang1_trans
                    self.message_queue.put(('info', f"🌍 Определен язык: {detected_lang}"))
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
                        self.message_queue.put(('info', f"✅ Определен язык: {detected_lang}"))
                        break
                    except sr.UnknownValueError:
                        continue

            if text and detected_lang:
                # Обрабатываем распознанный текст
                self.process_recognized_text(text, detected_lang, confidence)
            else:
                raise sr.UnknownValueError("Речь не распознана")

        except sr.UnknownValueError:
            raise
        except sr.RequestError as e:
            raise
        except Exception as e:
            print(f"❌ Ошибка распознавания: {e}")
            raise

    def detect_language_from_text(self, text):
        """Пытается определить язык текста"""
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

    def process_recognized_text(self, text, detected_lang, confidence=0.8):
        """Обрабатывает распознанный текст"""
        try:
            # Получаем коды языков
            lang1_trans, _ = self.get_language_code(self.lang1_combo.currentText())
            lang2_trans, _ = self.get_language_code(self.lang2_combo.currentText())

            # Определяем говорящего
            if detected_lang == lang1_trans:
                speaker = "Speaker 1"
                target_lang = lang2_trans
            elif detected_lang == lang2_trans:
                speaker = "Speaker 2"
                target_lang = lang1_trans
            else:
                # Если язык не совпадает, определяем по ближайшему
                speaker = "Speaker 1" if detected_lang == lang1_trans[:2] else "Speaker 2"
                target_lang = lang2_trans if speaker == "Speaker 1" else lang1_trans

            # Переводим текст
            self.message_queue.put(('status', f"🌐 Перевод..."))
            translated_text = self.translate_with_google_api(text, detected_lang, target_lang)

            # Создаем сообщение
            message = DialogueMessage(
                speaker=speaker,
                language=detected_lang,
                original_text=text,
                translated_text=translated_text,
                timestamp=datetime.now(),
                confidence=confidence
            )

            # Добавляем в очередь
            self.message_queue.put(('message', message))

            # Автоматически озвучиваем, если включено
            if self.config['enable_tts'] and self.config['auto_play_tts']:
                self.speak_text(translated_text, target_lang)

        except Exception as e:
            print(f"❌ Ошибка обработки текста: {e}")
            self.message_queue.put(('error', f"Ошибка: {str(e)[:30]}"))

    def translate_with_google_api(self, text, source_lang, target_lang):
        """Переводит текст через Google Translate API"""
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
                timeout=self.config['translation_timeout']
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

    def add_instruction_message(self):
        """Добавляет инструкцию"""
        instruction = (
            "🎤 ПЕРЕВОДЧИК С GOOGLE WEB SPEECH API + ELEVENLABS TTS\n\n"
            "1. Выберите языки и микрофон\n"
            "2. Нажмите 'НАЧАТЬ' для начала записи\n"
            "3. Говорите в микрофон\n"
            "4. Программа автоматически определит язык\n"
            "5. Перевод появится в чате\n"
            "6. Нажмите 🔊 чтобы озвучить перевод\n\n"
            "🔊 TTS - настройки ElevenLabs озвучивания\n"
            "⚙️ Основные настройки программы\n"
            "⛶ Переключение полного экрана\n"
            "✕ Закрыть приложение"
        )

        self.add_system_message(instruction)

    def add_system_message(self, text):
        """Добавляет системное сообщение"""
        message = DialogueMessage(
            speaker="System",
            language="info",
            original_text=text,
            translated_text="",
            timestamp=datetime.now(),
            confidence=1.0
        )

        self.display_message(message, is_system=True)

    def process_manual_input(self):
        """Обрабатывает ручной ввод текста"""
        if not self.config['enable_text_input']:
            return

        text = self.manual_input.text().strip()
        if not text:
            return

        try:
            # Определяем язык текста
            detected_lang = self.detect_language_from_text(text)
            if not detected_lang:
                # Если не удалось определить, используем первый язык
                detected_lang, _ = self.get_language_code(self.lang1_combo.currentText())

            # Получаем коды языков
            lang1_trans, _ = self.get_language_code(self.lang1_combo.currentText())
            lang2_trans, _ = self.get_language_code(self.lang2_combo.currentText())

            # Определяем говорящего
            if detected_lang == lang1_trans:
                speaker = "Speaker 1"
                target_lang = lang2_trans
            else:
                speaker = "Speaker 2"
                target_lang = lang1_trans

            # Переводим
            translated_text = self.translate_with_google_api(text, detected_lang, target_lang)

            # Создаем сообщение
            message = DialogueMessage(
                speaker=speaker,
                language=detected_lang,
                original_text=text,
                translated_text=translated_text,
                timestamp=datetime.now(),
                confidence=0.9
            )

            # Добавляем в очередь
            self.message_queue.put(('message', message))

            # Очищаем поле ввода
            self.manual_input.clear()
            self.manual_input.setFocus()

        except Exception as e:
            print(f"❌ Ошибка ручного ввода: {e}")
            self.message_queue.put(('error', f"Ошибка: {str(e)[:30]}"))

    def display_message(self, message, is_system=False):
        """Отображает сообщение в чате"""
        # Передаем self как parent_app для доступа к методу speak_text
        self.chat_widget.add_message(message, is_system, 
                                     speak_callback=self.speak_text if self.config['enable_tts'] else None,
                                     enable_tts=self.config['enable_tts'])

        # Добавляем в историю
        self.dialogue_history.append(message)

        # Обновляем статистику
        if not is_system and message.speaker in self.speaker_stats:
            self.speaker_stats[message.speaker] += 1

        # Ограничиваем историю
        if len(self.dialogue_history) > self.config['max_messages'] * 2:
            self.dialogue_history = self.dialogue_history[-self.config['max_messages']:]

        # Ограничиваем отображение сообщений
        self.chat_widget.limit_messages(self.config['max_messages'])

        # Обновляем статистику в заголовке
        self.update_stats_display()

    def update_stats_display(self):
        """Обновляет статистику в заголовке окна"""
        stats1 = self.speaker_stats['Speaker 1']
        stats2 = self.speaker_stats['Speaker 2']
        total = stats1 + stats2
        self.setWindowTitle(f"🎤 Переводчик (Speaker 1: {stats1} | Speaker 2: {stats2} | Всего: {total})")

    def clear_dialog(self):
        """Очищает диалог"""
        reply = QMessageBox.question(
            self, 'Очистка чата',
            'Вы уверены, что хотите очистить весь чат?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.dialogue_history.clear()
            self.chat_widget.clear_chat()
            self.speaker_stats = {'Speaker 1': 0, 'Speaker 2': 0}
            self.update_stats_display()
            self.add_instruction_message()
            self.message_queue.put(('info', "Чат очищен"))

    def export_dialog(self):
        """Экспортирует диалог в файл"""
        if not self.dialogue_history:
            self.message_queue.put(('error', "Диалог пуст"))
            return

        try:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Экспорт диалога", "dialog.txt",
                "Text files (*.txt);;All files (*.*)"
            )

            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("=" * 60 + "\n")
                    f.write("ЭКСПОРТ ДИАЛОГА ИЗ ПЕРЕВОДЧИКА\n")
                    f.write(f"Время экспорта: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 60 + "\n\n")

                    for message in self.dialogue_history:
                        if message.speaker != "System":
                            f.write(f"[{message.timestamp.strftime('%H:%M:%S')}] {message.speaker} ({message.language}):\n")
                            f.write(f"  Оригинал: {message.original_text}\n")
                            f.write(f"  Перевод: {message.translated_text}\n")
                            f.write("-" * 40 + "\n")

                self.message_queue.put(('info', f"✅ Диалог экспортирован в {filename}"))

        except Exception as e:
            print(f"❌ Ошибка экспорта: {e}")
            self.message_queue.put(('error', f"Ошибка экспорта: {str(e)[:30]}"))

    def stop_recording_thread(self):
        """Останавливает поток записи"""
        self.is_recording = False
        self.should_stop_recording.set()

        if self.recording_thread and self.recording_thread.is_alive():
            print("🛑 Остановка потока записи...")
            self.recording_thread.join(timeout=2)

    def update_ui(self):
        """Обновляет интерфейс"""
        try:
            while not self.message_queue.empty():
                msg_type, data = self.message_queue.get_nowait()

                if msg_type == 'time':
                    self.recording_time.setText(data)

                elif msg_type == 'message':
                    self.display_message(data)
                    self.update_stats_display()

                elif msg_type == 'status':
                    self.recognition_status.setText(data)

                elif msg_type == 'info':
                    self.recognition_status.setText(data)
                    QTimer.singleShot(2000, lambda:
                        self.recognition_status.setText("Готов"))

                elif msg_type == 'error':
                    self.recognition_status.setText(f"⚠️ {data}")

        except queue.Empty:
            pass

        # Обновляем визуализацию громкости
        if self.is_recording:
            import random
            if self.audio_stats['is_listening']:
                volume = random.randint(20, 90) if random.random() > 0.2 else random.randint(5, 30)
            else:
                volume = random.randint(0, 10)
            self.volume_meter.setValue(volume)

            # Мигание индикатора при прослушивании
            if self.audio_stats['is_listening']:
                if int(time.time() * 2) % 2 == 0:
                    self.listening_status.setText("🟢 СЛУШАЕТ")
                else:
                    self.listening_status.setText("🟢 Вкл.")
        else:
            self.volume_meter.setValue(0)

    def show_settings(self):
        """Показывает объединенные настройки (основные + TTS)"""
        dialog = QDialog(self)
        dialog.setWindowTitle("⚙️ Настройки")
        dialog.setFixedSize(550, 750)  # Увеличен размер для всех настроек
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        # Создаем переменную для хранения сообщения об ошибке
        self.tts_error_message = ""
        self.tts_test_in_progress = False

        # Применяем единый стиль
        dialog.setStyleSheet("""
            QDialog {
                background-color: rgba(25, 30, 40, 230);
                border-radius: 12px;
                border: 2px solid rgba(40, 45, 55, 200);
            }
            QLabel {
                color: #FFFFFF;
                font-size: 12px;
            }
            QPushButton {
                background-color: rgba(40, 45, 55, 200);
                color: white;
                border: 1px solid rgba(60, 65, 75, 200);
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 12px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: rgba(50, 55, 65, 200);
            }
            QPushButton:pressed {
                background-color: rgba(30, 35, 45, 200);
            }
            QLineEdit {
                background-color: rgba(40, 45, 55, 180);
                color: white;
                border: 1px solid rgba(60, 65, 75, 180);
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 12px;
                min-height: 32px;
            }
            QLineEdit:focus {
                border: 1px solid #6A1B9A;
            }
            QLineEdit::placeholder {
                color: #888888;
                font-style: italic;
            }
            QCheckBox {
                color: white;
                font-size: 12px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #6A1B9A;
                border-radius: 4px;
                background-color: rgba(40, 45, 55, 180);
            }
            QCheckBox::indicator:checked {
                background-color: #6A1B9A;
            }
            QSlider::groove:horizontal {
                background: rgba(40, 45, 55, 180);
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #6A1B9A;
                width: 18px;
                height: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }
            QSpinBox, QDoubleSpinBox {
                background-color: rgba(40, 45, 55, 180);
                color: white;
                border: 1px solid rgba(60, 65, 75, 180);
                border-radius: 4px;
                padding: 3px;
                font-size: 11px;
                min-width: 60px;
            }
            QGroupBox {
                color: #6A1B9A;
                font-weight: bold;
                border: 1px solid rgba(60, 65, 75, 100);
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 12px;
                font-size: 13px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollArea > QWidget > QWidget {
                background-color: transparent;
            }
            QComboBox {
                background-color: rgba(40, 45, 55, 180);
                color: white;
                border: 1px solid rgba(60, 65, 75, 180);
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QComboBox QAbstractItemView {
                background-color: rgba(40, 45, 55, 220);
                color: white;
                selection-background-color: #6A1B9A;
            }
            QTabWidget::pane {
                border: 1px solid rgba(60, 65, 75, 180);
                border-radius: 4px;
                background-color: rgba(25, 30, 40, 230);
            }
            QTabBar::tab {
                background-color: rgba(40, 45, 55, 180);
                color: white;
                padding: 8px 20px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: rgba(106, 27, 154, 200);
                color: white;
            }
            QTabBar::tab:hover {
                background-color: rgba(50, 55, 65, 200);
            }
        """)

        # Создаем вкладки для настроек
        tabs = QTabWidget()
        
        # ==== ВКЛАДКА 1: Основные настройки ====
        main_tab = QWidget()
        main_scroll = QScrollArea()
        main_scroll.setWidgetResizable(True)
        main_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        main_content = QWidget()
        main_layout = QVBoxLayout(main_content)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # ==== ВКЛАДКА 2: TTS настройки ====
        tts_tab = QWidget()
        tts_scroll = QScrollArea()
        tts_scroll.setWidgetResizable(True)
        tts_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        tts_content = QWidget()
        tts_layout = QVBoxLayout(tts_content)
        tts_layout.setSpacing(12)
        tts_layout.setContentsMargins(15, 15, 15, 15)
        
        # ==== Виджет статуса ошибок TTS (только для TTS вкладки) ====
        self.error_widget = QWidget()
        self.error_widget.setVisible(False)
        error_layout = QHBoxLayout(self.error_widget)
        error_layout.setContentsMargins(10, 8, 10, 8)

        error_icon = QLabel("⚠️")
        error_icon.setStyleSheet("font-size: 16px; color: #FFA726;")

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #FFA726; font-size: 12px;")
        self.error_label.setWordWrap(True)

        error_layout.addWidget(error_icon)
        error_layout.addWidget(self.error_label, 1)

        tts_layout.addWidget(self.error_widget)

        # ==== ГРУППА: Внешний вид ====
        appearance_group = QGroupBox("Внешний вид")
        appearance_layout = QGridLayout(appearance_group)
        appearance_layout.setVerticalSpacing(8)
        appearance_layout.setHorizontalSpacing(10)
        appearance_layout.setContentsMargins(12, 15, 12, 12)

        # Прозрачность окна
        appearance_layout.addWidget(QLabel("Прозрачность окна:"), 0, 0)

        opacity_slider = QSlider(Qt.Horizontal)
        opacity_slider.setRange(30, 100)
        opacity_slider.setValue(int(self.config['opacity'] * 100))

        self.opacity_value_label_main = QLabel(f"{int(self.config['opacity'] * 100)}%")
        self.opacity_value_label_main.setStyleSheet("color: #6A1B9A; font-weight: bold; min-width: 40px;")

        appearance_layout.addWidget(opacity_slider, 0, 1)
        appearance_layout.addWidget(self.opacity_value_label_main, 0, 2)

        opacity_slider.valueChanged.connect(lambda v: self.opacity_value_label_main.setText(f"{v}%"))
        opacity_slider.valueChanged.connect(lambda v: self.change_opacity(v))

        # Сообщений в чате
        appearance_layout.addWidget(QLabel("Сообщений в чате:"), 1, 0)

        messages_spin = QSpinBox()
        messages_spin.setRange(10, 200)
        messages_spin.setValue(self.config['max_messages'])
        messages_spin.setFixedWidth(70)

        appearance_layout.addWidget(messages_spin, 1, 1, 1, 2)

        messages_spin.valueChanged.connect(self.change_max_messages)

        main_layout.addWidget(appearance_group)

        # ==== ГРУППА: Распознавание речи ====
        recognition_group = QGroupBox("Распознавание речи")
        recognition_layout = QGridLayout(recognition_group)
        recognition_layout.setVerticalSpacing(8)
        recognition_layout.setHorizontalSpacing(10)
        recognition_layout.setContentsMargins(12, 15, 12, 12)

        # Автоопределение языка
        self.auto_detect_checkbox = QCheckBox("Автоопределение языка")
        self.auto_detect_checkbox.setChecked(self.config['auto_detect_language'])
        self.auto_detect_checkbox.stateChanged.connect(self.toggle_auto_detect)

        recognition_layout.addWidget(self.auto_detect_checkbox, 0, 0, 1, 3)

        # Порог энергии
        recognition_layout.addWidget(QLabel("Порог энергии:"), 1, 0)

        energy_slider = QSlider(Qt.Horizontal)
        energy_slider.setRange(100, 500)
        energy_slider.setValue(self.config['energy_threshold'])

        self.energy_value_label = QLabel(f"{self.config['energy_threshold']}")
        self.energy_value_label.setStyleSheet("color: #6A1B9A; font-weight: bold; min-width: 40px;")

        recognition_layout.addWidget(energy_slider, 1, 1)
        recognition_layout.addWidget(self.energy_value_label, 1, 2)

        energy_slider.valueChanged.connect(lambda v: self.energy_value_label.setText(f"{v}"))
        energy_slider.valueChanged.connect(lambda v: self.update_energy_threshold(v))

        # Порог паузы
        recognition_layout.addWidget(QLabel("Порог паузы:"), 2, 0)

        pause_spin = QDoubleSpinBox()
        pause_spin.setRange(0.5, 2.0)
        pause_spin.setSingleStep(0.1)
        pause_spin.setDecimals(2)
        pause_spin.setValue(self.config['pause_threshold'])
        pause_spin.setFixedWidth(70)

        recognition_layout.addWidget(pause_spin, 2, 1, 1, 2)

        pause_spin.valueChanged.connect(lambda v: self.update_pause_threshold(v))

        main_layout.addWidget(recognition_group)

        # ==== ГРУППА: Дополнительные функции ====
        features_group = QGroupBox("Дополнительные функции")
        features_layout = QVBoxLayout(features_group)
        features_layout.setSpacing(8)
        features_layout.setContentsMargins(12, 15, 12, 12)

        # Ручной ввод текста
        self.text_input_checkbox = QCheckBox("Ручной ввод текста")
        self.text_input_checkbox.setChecked(self.config['enable_text_input'])
        self.text_input_checkbox.stateChanged.connect(self.toggle_text_input)

        features_layout.addWidget(self.text_input_checkbox)

        # Информация о ручном вводе
        info_label = QLabel("Включает поле ввода внизу окна")
        info_label.setStyleSheet("color: #888888; font-size: 10px; padding-left: 24px; font-style: italic;")
        features_layout.addWidget(info_label)

        main_layout.addWidget(features_group)
        
        main_layout.addStretch()
        
        # Устанавливаем содержимое для вкладки "Основные"
        main_scroll.setWidget(main_content)
        main_tab_layout = QVBoxLayout(main_tab)
        main_tab_layout.setContentsMargins(0, 0, 0, 0)
        main_tab_layout.addWidget(main_scroll)

        # ==== ГРУППА: ElevenLabs TTS - Активация ====
        activation_group = QGroupBox("🔊 Озвучивание (ElevenLabs TTS)")
        activation_layout = QHBoxLayout(activation_group)
        activation_layout.setContentsMargins(12, 15, 12, 12)

        self.tts_enable_checkbox = QCheckBox("Включить озвучивание переводов")
        self.tts_enable_checkbox.setChecked(self.config['enable_tts'])
        self.tts_enable_checkbox.stateChanged.connect(
            lambda state: self.update_tts_setting('enable_tts', state == Qt.Checked))

        activation_layout.addWidget(self.tts_enable_checkbox)
        tts_layout.addWidget(activation_group)

        # ==== ГРУППА: ElevenLabs TTS - API Настройки ====
        api_group = QGroupBox("API Настройки")
        api_layout = QVBoxLayout(api_group)
        api_layout.setSpacing(8)
        api_layout.setContentsMargins(12, 15, 12, 12)

        api_label = QLabel("API Ключ ElevenLabs:")
        api_label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        api_layout.addWidget(api_label)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("sk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        self.api_key_input.setText(self.config['elevenlabs_api_key'])
        self.api_key_input.setEchoMode(QLineEdit.Password)
        api_layout.addWidget(self.api_key_input)

        info_widget = QWidget()
        info_layout = QHBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)

        key_icon = QLabel("🔑")
        key_icon.setStyleSheet("font-size: 14px;")

        info_text = QLabel(
            "<a href='https://elevenlabs.io/app' style='color: #6A1B9A;'>Получить ключ на elevenlabs.io/app</a>")
        info_text.setOpenExternalLinks(True)
        info_text.setStyleSheet("color: #888888; font-size: 11px; font-style: italic; margin-left: 5px;")

        info_layout.addWidget(key_icon)
        info_layout.addWidget(info_text)
        info_layout.addStretch()

        api_layout.addWidget(info_widget)
        tts_layout.addWidget(api_group)

        # ==== ГРУППА: ElevenLabs TTS - Модель ====
        model_group = QGroupBox("Модель TTS")
        model_layout = QVBoxLayout(model_group)
        model_layout.setSpacing(8)
        model_layout.setContentsMargins(12, 15, 12, 12)

        model_label = QLabel("Выберите модель для бесплатного тарифа:")
        model_label.setStyleSheet("font-weight: bold;")
        model_layout.addWidget(model_label)

        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "eleven_turbo_v2 - Fast & Free",
            "eleven_multilingual_v2 - Multilingual",
            "eleven_monolingual_v1 - Deprecated (не для free tier)"
        ])

        # Устанавливаем текущую модель
        current_model = self.config.get('tts_model', 'eleven_turbo_v2')
        if current_model == 'eleven_turbo_v2':
            self.model_combo.setCurrentIndex(0)
        elif current_model == 'eleven_multilingual_v2':
            self.model_combo.setCurrentIndex(1)
        else:
            self.model_combo.setCurrentIndex(2)

        self.model_combo.currentIndexChanged.connect(self.update_tts_model)
        model_layout.addWidget(self.model_combo)

        model_info = QLabel("Для бесплатного тарифа используйте eleven_turbo_v2 или eleven_multilingual_v2")
        model_info.setStyleSheet("color: #888888; font-size: 10px; font-style: italic;")
        model_layout.addWidget(model_info)

        tts_layout.addWidget(model_group)

        # ==== ГРУППА: ElevenLabs TTS - Настройки голоса ====
        voice_group = QGroupBox("Настройки голоса")
        voice_layout = QGridLayout(voice_group)
        voice_layout.setVerticalSpacing(10)
        voice_layout.setHorizontalSpacing(12)
        voice_layout.setContentsMargins(12, 15, 12, 12)

        # Громкость
        volume_label = QLabel("Громкость:")
        voice_layout.addWidget(volume_label, 0, 0)

        volume_slider = QSlider(Qt.Horizontal)
        volume_slider.setRange(0, 100)
        volume_slider.setValue(self.config['tts_volume'])

        self.volume_value_label = QLabel(f"{self.config['tts_volume']}%")
        self.volume_value_label.setStyleSheet("""
            color: #6A1B9A; 
            font-weight: bold; 
            min-width: 45px;
            font-size: 12px;
        """)

        volume_slider.valueChanged.connect(lambda v: self.volume_value_label.setText(f"{v}%"))
        volume_slider.valueChanged.connect(lambda v: self.update_tts_setting('tts_volume', v))

        voice_layout.addWidget(volume_slider, 0, 1)
        voice_layout.addWidget(self.volume_value_label, 0, 2)

        # Скорость
        speed_label = QLabel("Скорость:")
        voice_layout.addWidget(speed_label, 1, 0)

        speed_widget = QWidget()
        speed_widget_layout = QHBoxLayout(speed_widget)
        speed_widget_layout.setContentsMargins(0, 0, 0, 0)
        speed_widget_layout.setSpacing(6)

        speed_spin = QDoubleSpinBox()
        speed_spin.setRange(0.5, 2.0)
        speed_spin.setSingleStep(0.1)
        speed_spin.setDecimals(2)
        speed_spin.setValue(self.config['tts_speed'])
        speed_spin.setFixedWidth(70)

        speed_slider = QSlider(Qt.Horizontal)
        speed_slider.setRange(50, 200)  # 0.5-2.0 умноженное на 100
        speed_slider.setValue(int(self.config['tts_speed'] * 100))

        def update_speed_from_slider(value):
            speed = value / 100.0
            speed_spin.setValue(speed)
            self.update_tts_setting('tts_speed', speed)

        def update_slider_from_spin(value):
            speed_slider.setValue(int(value * 100))
            self.update_tts_setting('tts_speed', value)

        speed_slider.valueChanged.connect(update_speed_from_slider)
        speed_spin.valueChanged.connect(update_slider_from_spin)

        speed_widget_layout.addWidget(speed_spin)
        speed_widget_layout.addWidget(speed_slider)

        voice_layout.addWidget(speed_widget, 1, 1, 1, 2)

        # Voice ID с выбором из списка (QComboBox)
        voice_id_label = QLabel("Голос:")
        voice_layout.addWidget(voice_id_label, 2, 0)

        self.voice_combo = QComboBox()
        # НЕ делаем редактируемым - это обычный комбобокс с выпадающим списком
        self.voice_combo.setEditable(False)
        self.voice_combo.setStyleSheet("""
            QComboBox {
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 11px;
            }
            QComboBox QAbstractItemView {
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 11px;
            }
        """)
        
        # Подключаем сигнал выбора из списка
        self.voice_combo.activated.connect(self.on_voice_selected)
        
        # Сохраняем оригинальный метод showPopup
        original_show_popup = self.voice_combo.showPopup
        self._voice_combo_loading = False  # Флаг загрузки голосов
        
        # Переопределяем showPopup для загрузки голосов при открытии
        def show_popup_with_load():
            # Если список пуст и не идет загрузка, загружаем голоса
            if self.voice_combo.count() == 0 and not self._voice_combo_loading:
                self._voice_combo_loading = True
                self.load_voices_into_combo()
                # Не открываем popup сразу - он откроется после загрузки через сигнал
                return
            # Если список не пуст, открываем popup
            if self.voice_combo.count() > 0:
                original_show_popup()
        
        self.voice_combo.showPopup = show_popup_with_load
        self._voice_combo_loading = False  # Инициализируем флаг
        
        # Не добавляем временный элемент - комбобокс будет пустым до загрузки голосов
        
        voice_layout.addWidget(self.voice_combo, 2, 1, 1, 2)
        
        voice_id_info = QLabel("Нажмите на стрелку для выбора голоса из списка")
        voice_id_info.setStyleSheet("color: #888888; font-size: 10px; font-style: italic;")
        voice_layout.addWidget(voice_id_info, 3, 1, 1, 2)

        tts_layout.addWidget(voice_group)

        # ==== ГРУППА: ElevenLabs TTS - Автоматизация ====
        auto_group = QGroupBox("Автоматизация")
        auto_layout = QVBoxLayout(auto_group)
        auto_layout.setSpacing(8)
        auto_layout.setContentsMargins(12, 15, 12, 12)

        self.auto_play_checkbox = QCheckBox("Автоматически озвучивать новые сообщения")
        self.auto_play_checkbox.setChecked(self.config['auto_play_tts'])
        self.auto_play_checkbox.stateChanged.connect(
            lambda state: self.update_tts_setting('auto_play_tts', state == Qt.Checked))

        auto_note = QLabel("Будет автоматически озвучивать каждый новый перевод")
        auto_note.setStyleSheet("color: #888888; font-size: 11px; padding-left: 24px; font-style: italic;")

        auto_layout.addWidget(self.auto_play_checkbox)
        auto_layout.addWidget(auto_note)
        tts_layout.addWidget(auto_group)

        tts_layout.addStretch()
        
        # Устанавливаем содержимое для вкладки "TTS"
        tts_scroll.setWidget(tts_content)
        tts_tab_layout = QVBoxLayout(tts_tab)
        tts_tab_layout.setContentsMargins(0, 0, 0, 0)
        tts_tab_layout.addWidget(tts_scroll)
        
        # Добавляем вкладки
        tabs.addTab(main_tab, "📋 Основные")
        tabs.addTab(tts_tab, "🔊 TTS")

        # Основной layout диалога
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(tabs)

        # ==== Кнопки (внизу, вне scroll area) ====
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(15, 10, 15, 15)
        button_layout.setSpacing(12)

        # Кнопка теста TTS
        self.test_btn = QPushButton("🔊 Тест")
        self.test_btn.clicked.connect(lambda: self.test_tts_from_dialog(dialog))
        self.test_btn.setFixedWidth(90)
        self.test_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(106, 27, 154, 180);
                border: 1px solid rgba(106, 27, 154, 200);
            }
            QPushButton:hover {
                background-color: rgba(126, 47, 174, 180);
            }
        """)
        self.test_btn.setToolTip("Проверить озвучивание с текущими настройками")

        # Кнопка помощи
        help_btn = QPushButton("❓")
        help_btn.clicked.connect(lambda: self.show_tts_help())
        help_btn.setFixedWidth(36)
        help_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(40, 45, 55, 180);
                border: 1px solid rgba(60, 65, 75, 200);
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(50, 55, 65, 180);
            }
        """)
        help_btn.setToolTip("Помощь по настройкам")

        # Основные кнопки
        ok_btn = QPushButton("✅ Применить")
        ok_btn.clicked.connect(lambda: self.save_all_settings(dialog))
        ok_btn.setFixedWidth(110)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(106, 27, 154, 200);
                border: 1px solid rgba(106, 27, 154, 220);
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(126, 47, 174, 200);
            }
        """)

        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.clicked.connect(dialog.reject)
        cancel_btn.setFixedWidth(110)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 107, 107, 180);
                border: 1px solid rgba(255, 107, 107, 200);
            }
            QPushButton:hover {
                background-color: rgba(255, 127, 127, 180);
            }
        """)

        button_layout.addWidget(self.test_btn)
        button_layout.addWidget(help_btn)
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(ok_btn)

        main_layout.addWidget(button_widget)

        dialog.exec_()

    def save_all_settings(self, dialog):
        """Сохраняет все настройки (основные + TTS) и закрывает диалог"""
        try:
            # Сохраняем TTS настройки
            self.config['elevenlabs_api_key'] = self.api_key_input.text()
            
            # Получаем voice_id из комбобокса
            current_index = self.voice_combo.currentIndex()
            if current_index >= 0:
                voice_id = self.voice_combo.itemData(current_index)
                if voice_id:
                    self.config['tts_voice_id'] = voice_id
                else:
                    # Если данных нет, используем текст (на случай ручного ввода, если комбобокс редактируемый)
                    self.config['tts_voice_id'] = self.voice_combo.currentText()
            else:
                # Если ничего не выбрано, используем текущий текст
                self.config['tts_voice_id'] = self.voice_combo.currentText()
            
            # Сохраняем конфигурацию (включая секреты)
            save_config(self.config)
            dialog.accept()
            self.message_queue.put(('info', "✅ Все настройки сохранены"))
        except Exception as e:
            print(f"❌ DEBUG: Ошибка сохранения настроек: {e}")
            import traceback
            print(traceback.format_exc())
            QMessageBox.warning(self, "Ошибка", f"Ошибка сохранения настроек: {str(e)}")

    def change_max_messages(self, value):
        """Изменяет максимальное количество сообщений"""
        self.config['max_messages'] = value
        self.chat_widget.limit_messages(value)
        save_config(self.config)  # Сохраняем конфиг
        self.message_queue.put(('info', f"💬 Макс. сообщений: {value}"))

    def change_opacity(self, value):
        """Изменяет прозрачность"""
        opacity = value / 100.0
        self.setWindowOpacity(opacity)
        self.config['opacity'] = opacity
        save_config(self.config)  # Сохраняем конфиг

    def toggle_text_input(self, state):
        """Включает/выключает ручной ввод"""
        self.config['enable_text_input'] = (state == Qt.Checked)
        self.manual_input.setVisible(self.config['enable_text_input'])
        self.send_btn.setVisible(self.config['enable_text_input'])
        save_config(self.config)  # Сохраняем конфиг

        if self.config['enable_text_input']:
            self.message_queue.put(('info', "✅ Ручной ввод включен"))
        else:
            self.message_queue.put(('info', "⏸️ Ручной ввод выключен"))

    def toggle_auto_detect(self, state):
        """Включает/выключает автоопределение языка"""
        self.config['auto_detect_language'] = (state == Qt.Checked)
        save_config(self.config)  # Сохраняем конфиг
        if self.config['auto_detect_language']:
            self.message_queue.put(('info', "✅ Автоопределение языка включено"))
        else:
            self.message_queue.put(('info', "⏸️ Автоопределение языка выключено"))

    def update_energy_threshold(self, value):
        """Обновляет порог энергии"""
        self.config['energy_threshold'] = value
        if self.recognizer:
            self.recognizer.energy_threshold = value
        save_config(self.config)  # Сохраняем конфиг

    def update_pause_threshold(self, value):
        """Обновляет порог паузы"""
        self.config['pause_threshold'] = value
        if self.recognizer:
            self.recognizer.pause_threshold = value
        save_config(self.config)  # Сохраняем конфиг

    def on_voice_selected(self, index):
        """Обрабатывает выбор голоса из комбобокса"""
        if index >= 0:
            voice_id = self.voice_combo.itemData(index)
            if voice_id:
                self.update_tts_setting('tts_voice_id', voice_id)
                self.message_queue.put(('info', f"✅ Выбран голос: {self.voice_combo.currentText()}"))
    
    def on_voice_text_changed(self, text):
        """Обрабатывает изменение текста в комбобоксе (ручной ввод)"""
        if text and not self.voice_combo.itemData(self.voice_combo.currentIndex()):
            # Если текст введен вручную, сохраняем его как ID
            self.update_tts_setting('tts_voice_id', text)
    
    def load_voices_into_combo(self):
        """Загружает список голосов из ElevenLabs API в комбобокс"""
        api_key = self.config.get('elevenlabs_api_key', '').strip()
        if not api_key:
            QMessageBox.warning(self, "Ошибка", 
                "API ключ ElevenLabs не установлен.\n\n"
                "Введите ключ в настройках перед выбором голоса.")
            return
        
        if not api_key.startswith("sk_"):
            QMessageBox.warning(self, "Ошибка", 
                "Неверный формат API ключа.\n\n"
                "Ключ должен начинаться с 'sk_'")
            return
        
        # Показываем прогресс
        self.message_queue.put(('status', "🔍 Загрузка списка голосов..."))
        
        # Загружаем голоса в отдельном потоке
        def load_voices():
            try:
                url = "https://api.elevenlabs.io/v1/voices"
                headers = {
                    "xi-api-key": api_key
                }
                
                print(f"🔊 DEBUG: Запрос списка голосов...")
                response = requests.get(url, headers=headers, timeout=10)
                print(f"🔊 DEBUG: Статус ответа: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    voices = data.get('voices', [])
                    print(f"🔊 DEBUG: Получено голосов: {len(voices)}")
                    if voices:
                        print(f"🔊 DEBUG: Первый голос: {voices[0].get('name', 'N/A')}")
                    
                    # Передаем результат в главный поток через сигнал
                    print(f"🔊 DEBUG: Отправляю сигнал с {len(voices)} голосами")
                    self.voices_loaded.emit(voices)
                elif response.status_code == 401:
                    error_text = response.text
                    print(f"❌ DEBUG: 401 ошибка: {error_text}")
                    error_msg = "Неверный API ключ ElevenLabs."
                    QTimer.singleShot(0, lambda: QMessageBox.warning(self, "Ошибка", error_msg))
                else:
                    error_text = response.text[:100] if response.text else ""
                    error_msg = f"Ошибка загрузки голосов: {response.status_code}\n{error_text}"
                    print(f"❌ DEBUG: Ошибка {response.status_code}: {error_text}")
                    QTimer.singleShot(0, lambda: QMessageBox.warning(self, "Ошибка", error_msg))
            except requests.exceptions.RequestException as e:
                error_msg = f"Ошибка сети при загрузке голосов: {str(e)}"
                print(f"❌ DEBUG: {error_msg}")
                QTimer.singleShot(0, lambda: QMessageBox.warning(self, "Ошибка", error_msg))
            except Exception as e:
                error_msg = f"Ошибка при загрузке голосов: {str(e)}"
                print(f"❌ DEBUG: {error_msg}")
                import traceback
                print(traceback.format_exc())
                QTimer.singleShot(0, lambda: QMessageBox.warning(self, "Ошибка", error_msg))
        
        threading.Thread(target=load_voices, daemon=True).start()
    
    def show_voice_selection_dialog(self, voices):
        """Заполняет комбобокс списком голосов (вызывается через сигнал из потока)"""
        print(f"🔊 DEBUG: Заполняю комбобокс с {len(voices) if voices else 0} голосами")
        if not voices:
            print("❌ DEBUG: Список голосов пуст")
            # Добавляем сообщение в комбобокс
            self.voice_combo.clear()
            self.voice_combo.addItem("Голоса не найдены", "")
            QMessageBox.information(self, "Информация", "Голоса не найдены.")
            return
        
        # Очищаем комбобокс
        self.voice_combo.clear()
        
        # Добавляем голоса в комбобокс
        current_voice_id = self.config.get('tts_voice_id', '')
        current_index = 0
        
        for i, voice in enumerate(voices):
            voice_id = voice.get('voice_id', '')
            name = voice.get('name', 'Без имени')
            description = voice.get('description', '')
            
            # Формируем текст для отображения
            if description:
                display_text = f"{name} - {description}"
            else:
                display_text = name
            
            # Добавляем в комбобокс с ID в данных
            self.voice_combo.addItem(display_text, voice_id)
            print(f"🔊 DEBUG: Добавлен голос {i+1}/{len(voices)}: {display_text[:50]}")
            
            # Если это текущий выбранный голос, запоминаем индекс
            if voice_id == current_voice_id:
                current_index = i
        
        # Проверяем количество элементов в комбобоксе
        combo_count = self.voice_combo.count()
        print(f"🔊 DEBUG: В комбобоксе элементов: {combo_count}, ожидалось: {len(voices)}")
        
        # Устанавливаем текущий выбор
        if current_voice_id and current_index < combo_count:
            self.voice_combo.setCurrentIndex(current_index)
        elif combo_count > 0:
            # Если текущий голос не найден, выбираем первый
            self.voice_combo.setCurrentIndex(0)
        
        print(f"🔊 DEBUG: Комбобокс заполнен. Всего элементов: {self.voice_combo.count()}")
        self.message_queue.put(('info', f"✅ Загружено {combo_count} голосов"))
        
        # Сбрасываем флаг загрузки
        self._voice_combo_loading = False
        
        # НЕ открываем popup автоматически - пользователь сам откроет его при необходимости

    def mousePressEvent(self, event):
        """Перетаскивание окна"""
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        """Перетаскивание окна"""
        if event.buttons() == Qt.LeftButton and hasattr(self, 'drag_pos'):
            self.move(event.globalPos() - self.drag_pos)

    def closeEvent(self, event):
        """Обработка закрытия окна"""
        self.stop_recording_thread()
        # Сохраняем конфигурацию при закрытии приложения (включая секреты)
        save_config(self.config)
        event.accept()

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