"""Виджет чата для отображения сообщений диалога"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel, QPushButton
from PyQt5.QtCore import Qt, QTimer
from app.models.dialogue import DialogueMessage


class ChatWidget(QWidget):
    """Виджет чата как в Telegram"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Настройка интерфейса чата"""
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
    
    def add_message(self, message: DialogueMessage, is_system: bool = False, speak_callback=None, enable_tts: bool = False):
        """
        Добавляет сообщение в чат
        
        Args:
            message: Сообщение для отображения
            is_system: Системное ли сообщение
            speak_callback: Функция для озвучивания (text, lang)
            enable_tts: Включено ли TTS
        """
        # Создаем виджет сообщения
        message_widget = self.create_message_widget(message, is_system, speak_callback, enable_tts)
        
        # Вставляем перед растягивающимся элементом
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, message_widget)
        
        # Прокручиваем к новому сообщению
        QTimer.singleShot(50, self.scroll_to_bottom)
    
    def create_message_widget(self, message: DialogueMessage, is_system: bool = False, 
                             speak_callback=None, enable_tts: bool = False):
        """
        Создает виджет сообщения с кнопкой озвучивания
        
        Args:
            message: Сообщение
            is_system: Системное ли сообщение
            speak_callback: Функция для озвучивания (text, lang)
            enable_tts: Включено ли TTS
        """
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
            
            # Перевод с кнопкой озвучивания
            translation_widget = QWidget()
            translation_layout = QHBoxLayout(translation_widget)
            translation_layout.setContentsMargins(0, 0, 0, 0)
            translation_layout.setSpacing(8)
            
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
            
            # Кнопка озвучивания
            if speak_callback and enable_tts and message.translated_text:
                tts_btn = QPushButton("🔊")
                tts_btn.setFixedSize(24, 24)
                tts_btn.setCursor(Qt.PointingHandCursor)
                tts_btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(78, 205, 196, 0.3);
                        border: 1px solid rgba(78, 205, 196, 0.5);
                        border-radius: 12px;
                        color: white;
                        font-size: 10px;
                    }
                    QPushButton:hover {
                        background-color: rgba(78, 205, 196, 0.5);
                        border: 1px solid rgba(78, 205, 196, 0.7);
                    }
                    QPushButton:pressed {
                        background-color: rgba(78, 205, 196, 0.7);
                    }
                """)
                tts_btn.setToolTip("Озвучить перевод")
                
                # Подключаем callback
                tts_btn.clicked.connect(lambda checked, text=message.translated_text,
                                                lang=message.language:
                                        speak_callback(text, lang))
                
                translation_layout.addWidget(translated_text, 1)
                translation_layout.addWidget(tts_btn)
            else:
                translation_layout.addWidget(translated_text)
            
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
            content.addWidget(translation_widget)
            content.addLayout(footer)
            
            # Добавляем контент в основной layout
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
    
    def limit_messages(self, max_messages: int):
        """
        Ограничивает количество сообщений в чате
        
        Args:
            max_messages: Максимальное количество сообщений
        """
        while self.chat_layout.count() > max_messages + 1:  # +1 для растягивающегося элемента
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
