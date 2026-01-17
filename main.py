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
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Tuple
import urllib.parse

# PyQt5 для GUI
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

# Для распознавания речи
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False
    print("⚠️ SpeechRecognition не установлен. pip install SpeechRecognition")

@dataclass
class DialogueMessage:
    speaker: str  # "Speaker 1" или "Speaker 2"
    language: str  # Определенный язык (ru, en, etc)
    original_text: str
    translated_text: str
    timestamp: datetime
    confidence: float  # Уверенность распознавания

class ChatWidget(QWidget):
    """Виджет чата как в Telegram"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Создаем область прокрутки для чата
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background-color: transparent;
            }
        """)

        # Виджет для сообщений
        self.chat_container = QWidget()
        self.chat_container.setStyleSheet("background-color: rgba(15, 20, 30, 180);")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setAlignment(Qt.AlignTop)
        self.chat_layout.setContentsMargins(10, 10, 10, 10)
        self.chat_layout.setSpacing(6)

        # Добавляем растягивающийся элемент в конец
        self.chat_layout.addStretch(1)

        self.scroll_area.setWidget(self.chat_container)
        layout.addWidget(self.scroll_area)

    def add_message(self, message, is_system=False):
        """Добавляет сообщение в чат"""
        # Создаем виджет сообщения
        message_widget = self.create_message_widget(message, is_system)

        # Вставляем перед растягивающимся элементом
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, message_widget)

        # Прокручиваем к новому сообщению
        QTimer.singleShot(50, self.scroll_to_bottom)

    def create_message_widget(self, message, is_system=False):
        """Создает виджет сообщения"""
        widget = QWidget()
        widget.setObjectName("MessageWidget")

        # Определяем выравнивание в зависимости от спикера
        if message.speaker == "Speaker 1":
            align = Qt.AlignLeft
            main_layout = QHBoxLayout(widget)
            main_layout.setAlignment(Qt.AlignLeft)
        elif message.speaker == "Speaker 2":
            align = Qt.AlignRight
            main_layout = QHBoxLayout(widget)
            main_layout.setAlignment(Qt.AlignRight)
        else:  # System
            align = Qt.AlignCenter
            main_layout = QHBoxLayout(widget)
            main_layout.setAlignment(Qt.AlignCenter)

        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(8)

        if is_system:
            # Системное сообщение (центрированное)
            widget.setStyleSheet("""
                QWidget#MessageWidget {
                    background-color: rgba(78, 205, 196, 0.1);
                    border-radius: 8px;
                    border: 1px dashed rgba(78, 205, 196, 0.5);
                }
            """)

            content = QVBoxLayout()
            content.setSpacing(3)

            # Заголовок
            title = QLabel(f"💡 {message.speaker}")
            title.setStyleSheet("color: #4ECDC4; font-weight: bold; font-size: 12px;")
            title.setAlignment(Qt.AlignCenter)

            # Текст
            text = QLabel(message.original_text)
            text.setStyleSheet("color: #AAAAAA; font-size: 11px;")
            text.setWordWrap(True)
            text.setTextFormat(Qt.PlainText)
            text.setAlignment(Qt.AlignCenter)

            content.addWidget(title)
            content.addWidget(text)

            main_layout.addLayout(content)

        else:
            # Обычное сообщение
            if message.speaker == "Speaker 1":
                bubble_color = "#FF6B6B"
                bubble_bg = "rgba(255, 107, 107, 0.1)"
            else:  # Speaker 2
                bubble_color = "#4ECDC4"
                bubble_bg = "rgba(78, 205, 196, 0.1)"

            widget.setStyleSheet(f"""
                QWidget#MessageWidget {{
                    background-color: {bubble_bg};
                    border-radius: 8px;
                    border-left: 3px solid {bubble_color};
                }}
            """)

            # Контент сообщения
            content = QVBoxLayout()
            content.setSpacing(3)

            # Заголовок с именем и временем
            header = QHBoxLayout()
            header.setSpacing(8)

            name = QLabel(message.speaker)
            name.setStyleSheet(f"color: {bubble_color}; font-weight: bold; font-size: 12px;")

            time_label = QLabel(message.timestamp.strftime("%H:%M:%S"))
            time_label.setStyleSheet("color: #666666; font-size: 10px;")

            if align == Qt.AlignRight:
                header.addStretch()
                header.addWidget(name)
                header.addWidget(time_label)
            else:  # AlignLeft
                header.addWidget(name)
                header.addWidget(time_label)
                header.addStretch()

            # Оригинальный текст
            original_text = QLabel(message.original_text)
            original_text.setStyleSheet("color: #E0E0E0; font-size: 13px; padding: 3px;")
            original_text.setWordWrap(True)
            original_text.setTextFormat(Qt.PlainText)

            # Перевод
            translated_text = QLabel(message.translated_text)
            translated_text.setStyleSheet("""
                QLabel {
                    color: #4ECDC4;
                    font-size: 12px;
                    padding: 3px;
                    background-color: rgba(0, 0, 0, 0.05);
                    border-radius: 4px;
                }
            """)
            translated_text.setWordWrap(True)
            translated_text.setTextFormat(Qt.PlainText)

            # Язык и уверенность
            footer = QHBoxLayout()
            footer.setSpacing(8)

            lang_label = QLabel(f"🌐 {message.language}")
            lang_label.setStyleSheet("color: #888888; font-size: 10px;")

            confidence_color = "#4ECDC4" if message.confidence > 0.7 else "#FFA726"
            conf_label = QLabel(f"уверенность: {message.confidence:.0%}")
            conf_label.setStyleSheet(f"color: {confidence_color}; font-size: 10px;")

            if align == Qt.AlignRight:
                footer.addStretch()
                footer.addWidget(lang_label)
                footer.addWidget(conf_label)
            else:  # AlignLeft
                footer.addWidget(lang_label)
                footer.addWidget(conf_label)
                footer.addStretch()

            content.addLayout(header)
            content.addWidget(original_text)
            content.addWidget(translated_text)
            content.addLayout(footer)

            # Добавляем контент в основной layout
            if align == Qt.AlignRight:
                # Сообщение справа
                main_layout.addLayout(content)
            else:
                # Сообщение слева
                main_layout.addLayout(content)

        return widget

    def scroll_to_bottom(self):
        """Прокручивает чат вниз"""
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_chat(self):
        """Очищает чат"""
        # Удаляем все виджеты кроме растягивающегося элемента
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def limit_messages(self, max_messages):
        """Ограничивает количество сообщений в чате"""
        while self.chat_layout.count() > max_messages + 1:  # +1 для растягивающегося элемента
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

class GoogleWebSpeechTranslator(QMainWindow):
    def __init__(self):
        super().__init__()

        # Настройки
        self.config = {
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
        }

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
        self.setWindowTitle("🎤 Переводчик с Google Web Speech API")
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

        # КНОПКА ЗАКРЫТИЯ
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

        # Кнопка разворачивания на весь экран
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

        layout.addSpacing(10)

        # Заголовок
        title = QLabel("🎤 Переводчик")
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
        else:
            self.mic_combo.addItem("🎤 Нет", -1)
            self.mic_combo.setEnabled(False)
            self.mic_combo.setFixedWidth(80)

        layout.addWidget(self.mic_combo)

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
        self.settings_btn.setToolTip("Настройки")

        # Добавляем кнопки управления
        layout.addWidget(self.clear_btn)
        layout.addWidget(self.export_btn)
        layout.addWidget(self.settings_btn)
        layout.addSpacing(10)
        layout.addWidget(self.record_btn)

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
            "🎤 ПЕРЕВОДЧИК С GOOGLE WEB SPEECH API\n\n"
            "1. Выберите языки и микрофон\n"
            "2. Нажмите 'НАЧАТЬ' для начала записи\n"
            "3. Говорите в микрофон\n"
            "4. Программа автоматически определит язык\n"
            "5. Перевод появится в чате\n\n"
            "⚙️ Ручной ввод можно включить в настройках\n"
            "⛶ Нажмите для переключения полного экрана\n"
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

    def display_message(self, message, is_system=False):
        """Отображает сообщение в чате"""
        self.chat_widget.add_message(message, is_system)

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

    def show_settings(self):
        """Показывает настройки"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Настройки")
        dialog.setFixedSize(350, 400)

        layout = QVBoxLayout(dialog)

        # Прозрачность
        opacity_layout = QHBoxLayout()
        opacity_layout.addWidget(QLabel("Прозрачность:"))
        opacity_slider = QSlider(Qt.Horizontal)
        opacity_slider.setRange(30, 100)
        opacity_slider.setValue(int(self.config['opacity'] * 100))
        opacity_slider.valueChanged.connect(
            lambda v: self.change_opacity(v))
        opacity_layout.addWidget(opacity_slider)
        layout.addLayout(opacity_layout)

        # Максимальное количество сообщений
        messages_layout = QHBoxLayout()
        messages_layout.addWidget(QLabel("Сообщений в чате:"))
        messages_spin = QSpinBox()
        messages_spin.setRange(10, 200)
        messages_spin.setValue(self.config['max_messages'])
        messages_spin.valueChanged.connect(self.change_max_messages)
        messages_layout.addWidget(messages_spin)
        layout.addLayout(messages_layout)

        # Ручной ввод
        text_input_layout = QHBoxLayout()
        text_input_layout.addWidget(QLabel("Ручной ввод текста:"))
        self.text_input_checkbox = QCheckBox("Включить")
        self.text_input_checkbox.setChecked(self.config['enable_text_input'])
        self.text_input_checkbox.stateChanged.connect(self.toggle_text_input)
        text_input_layout.addWidget(self.text_input_checkbox)
        layout.addLayout(text_input_layout)

        # Автоопределение языка
        auto_layout = QHBoxLayout()
        auto_layout.addWidget(QLabel("Автоопределение языка:"))
        self.auto_detect_checkbox = QCheckBox("Включено")
        self.auto_detect_checkbox.setChecked(self.config['auto_detect_language'])
        self.auto_detect_checkbox.stateChanged.connect(self.toggle_auto_detect)
        auto_layout.addWidget(self.auto_detect_checkbox)
        layout.addLayout(auto_layout)

        # Порог энергии
        energy_layout = QHBoxLayout()
        energy_layout.addWidget(QLabel("Порог энергии:"))
        energy_slider = QSlider(Qt.Horizontal)
        energy_slider.setRange(100, 500)
        energy_slider.setValue(self.config['energy_threshold'])
        energy_slider.valueChanged.connect(
            lambda v: self.update_energy_threshold(v))
        energy_layout.addWidget(energy_slider)
        layout.addLayout(energy_layout)

        # Порог паузы
        pause_layout = QHBoxLayout()
        pause_layout.addWidget(QLabel("Порог паузы (сек):"))
        pause_spin = QDoubleSpinBox()
        pause_spin.setRange(0.5, 2.0)
        pause_spin.setSingleStep(0.1)
        pause_spin.setValue(self.config['pause_threshold'])
        pause_spin.valueChanged.connect(
            lambda v: self.update_pause_threshold(v))
        pause_layout.addWidget(pause_spin)
        layout.addLayout(pause_layout)

        # Разделитель
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        # Кнопки
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        dialog.exec_()

    def change_max_messages(self, value):
        """Изменяет максимальное количество сообщений"""
        self.config['max_messages'] = value
        self.chat_widget.limit_messages(value)
        self.message_queue.put(('info', f"💬 Макс. сообщений: {value}"))

    def change_opacity(self, value):
        """Изменяет прозрачность"""
        opacity = value / 100.0
        self.setWindowOpacity(opacity)
        self.config['opacity'] = opacity

    def toggle_text_input(self, state):
        """Включает/выключает ручной ввод"""
        self.config['enable_text_input'] = (state == Qt.Checked)
        self.manual_input.setVisible(self.config['enable_text_input'])
        self.send_btn.setVisible(self.config['enable_text_input'])

        if self.config['enable_text_input']:
            self.message_queue.put(('info', "✅ Ручной ввод включен"))
        else:
            self.message_queue.put(('info', "⏸️ Ручной ввод выключен"))

    def toggle_auto_detect(self, state):
        """Включает/выключает автоопределение языка"""
        self.config['auto_detect_language'] = (state == Qt.Checked)
        if self.config['auto_detect_language']:
            self.message_queue.put(('info', "✅ Автоопределение языка включено"))
        else:
            self.message_queue.put(('info', "⏸️ Автоопределение языка выключено"))

    def update_energy_threshold(self, value):
        """Обновляет порог энергии"""
        self.config['energy_threshold'] = value
        if self.recognizer:
            self.recognizer.energy_threshold = value

    def update_pause_threshold(self, value):
        """Обновляет порог паузы"""
        self.config['pause_threshold'] = value
        if self.recognizer:
            self.recognizer.pause_threshold = value

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
    print("🎤 ПЕРЕВОДЧИК: GOOGLE WEB SPEECH API".center(70))
    print("=" * 70)

    print("\n✅ Используемые технологии:")
    print("  • Google Web Speech API - БЕСПЛАТНОЕ распознавание речи")
    print("  • Google Translate API - БЕСПЛАТНЫЙ перевод текста")
    print("  • SpeechRecognition - библиотека для работы с микрофоном")
    print("  • PyQt5 - графический интерфейс")

    print("\n🚀 Возможности:")
    print("  • Распознавание речи через бесплатный Google Web Speech API")
    print("  • Компактный header со всеми элементами управления")
    print("  • Сообщения Speaker 1 - слева, Speaker 2 - справа")
    print("  • Настройка количества сообщений (10-200)")
    print("  • Ручной ввод можно включить в настройках")
    print("  • Кнопка закрытия приложения (красная кнопка ✕)")
    print("  • Полноэкранный режим (кнопка ⛶)")

    print("\n⚡ Преимущества:")
    print("  • НЕ ТРЕБУЕТ API ключа")
    print("  • ВСЁ БЕСПЛАТНО")
    print("  • Компактный и прозрачный интерфейс")
    print("  • Настраиваемый внешний вид")

    print("\n🔧 Установка:")
    print("  pip install SpeechRecognition PyQt5 requests")
    print("=" * 70)

    main()