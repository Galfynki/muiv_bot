import sys
import requests
from bs4 import BeautifulSoup
import json
import os
from urllib.parse import urljoin, urlparse
import time
from pathlib import Path
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from transformers import pipeline, AutoTokenizer, AutoModelForQuestionAnswering
import torch
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QWidget, QPushButton, QTextEdit, QLabel, QProgressBar,
                             QLineEdit, QMessageBox, QSplitter, QFrame)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QPalette, QColor, QPixmap
import threading


class ParserThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)
    log_message = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.urls = [
            "https://www.muiv.ru/abitur/",
            "https://www.muiv.ru/studentu/"
        ]

    def run(self):
        self.parse_all()

    def get_page_content(self, url):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response.text
        except Exception as e:
            self.log_message.emit(f"Ошибка при загрузке {url}: {e}")
            return None

    def clean_text(self, text):
        text = ' '.join(text.split())
        import re
        text = re.sub(r'[^\w\s\u0400-\u04FF\.,!?():;—–-]', ' ', text)
        return text.strip()

    def parse_page(self, url, filename, data_dir):
        html_content = self.get_page_content(url)
        if not html_content:
            return None

        soup = BeautifulSoup(html_content, 'html.parser')

        with open(f"{data_dir}/{filename}.html", 'w', encoding='utf-8') as f:
            f.write(html_content)

        main_content = soup.find('main') or soup.find('div', class_='content') or soup.body
        text_content = self.clean_text(main_content.get_text() if main_content else soup.get_text())

        headings = {}
        for tag in soup.find_all(['h1', 'h2', 'h3', 'h4']):
            headings[tag.name] = self.clean_text(tag.get_text())

        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if not href.startswith('http'):
                href = urljoin(url, href)
            links.append({'text': self.clean_text(a.get_text()), 'url': href})

        page_data = {
            'url': url,
            'title': soup.title.string if soup.title else '',
            'headings': headings,
            'text_content': text_content,
            'links': links[:50]
        }

        with open(f"{data_dir}/{filename}.json", 'w', encoding='utf-8') as f:
            json.dump(page_data, f, ensure_ascii=False, indent=2)

        self.log_message.emit(f"✅ Сохранено: {filename}")
        return page_data

    def parse_all(self):
        data_dir = "muiv_data"
        os.makedirs(data_dir, exist_ok=True)
        all_data = {}

        for i, url in enumerate(self.urls):
            self.progress.emit(int((i / len(self.urls)) * 100))
            filename = f"page_{i + 1}_{urlparse(url).path.replace('/', '_').strip('_')}"
            page_data = self.parse_page(url, filename, data_dir)
            if page_data:
                all_data[url] = page_data
            time.sleep(1)

        self.progress.emit(100)
        self.finished.emit(all_data)


class MUIvChatBot:
    def __init__(self, data_dir="muiv_data"):
        self.data_dir = Path(data_dir)
        self.model = None
        self.qa_pipeline = None
        self.tokenizer = None
        self.qa_model = None
        self.documents = []
        self.embeddings = []

    def load_model(self):
        try:
            # Загружаем модель для эмбеддингов
            self.model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')

            # Загружаем русскую модель для вопросов-ответов
            self.tokenizer = AutoTokenizer.from_pretrained("AlexKay/xlm-roberta-large-qa-multilingual-finedtuned-ru")
            self.qa_model = AutoModelForQuestionAnswering.from_pretrained(
                "AlexKay/xlm-roberta-large-qa-multilingual-finedtuned-ru")

            # Создаем pipeline
            self.qa_pipeline = pipeline(
                "question-answering",
                model=self.qa_model,
                tokenizer=self.tokenizer,
                device=0 if torch.cuda.is_available() else -1
            )
            return True
        except Exception as e:
            print(f"Ошибка загрузки моделей: {e}")
            # Пробуем альтернативную модель
            try:
                model_name = "abletobetable/distilbert-ru-qa"
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.qa_model = AutoModelForQuestionAnswering.from_pretrained(model_name)
                self.qa_pipeline = pipeline(
                    "question-answering",
                    model=self.qa_model,
                    tokenizer=self.tokenizer,
                    device=0 if torch.cuda.is_available() else -1
                )
                return True
            except Exception as e2:
                print(f"Ошибка загрузки альтернативной модели: {e2}")
                return False

    def load_documents(self):
        self.documents = []
        self.embeddings = []

        for json_file in self.data_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                text = data.get('text_content', '')
                chunks = self.split_text(text, chunk_size=500, overlap=50)

                for i, chunk in enumerate(chunks):
                    self.documents.append({
                        'content': chunk,
                        'source': data['url'],
                        'title': data.get('title', ''),
                        'chunk_id': f"{json_file.stem}_{i}"
                    })
            except Exception as e:
                print(f"Ошибка загрузки {json_file}: {e}")

        if self.model and self.documents:
            texts = [doc['content'] for doc in self.documents]
            self.embeddings = self.model.encode(texts, show_progress_bar=True)
        return len(self.documents)

    def split_text(self, text, chunk_size=500, overlap=50):
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk = ' '.join(words[i:i + chunk_size])
            if len(chunk) > 20:
                chunks.append(chunk)
        return chunks

    def find_relevant_docs(self, query, top_k=5):
        if not self.model or not len(self.embeddings):
            return []
        query_embedding = self.model.encode([query])
        similarities = cosine_similarity(query_embedding, self.embeddings)[0]
        top_indices = np.argsort(similarities)[::-1][:top_k]
        return [self.documents[idx] for idx in top_indices if similarities[idx] > 0.1]

    def answer_question(self, question):
        if not self.qa_pipeline:
            return "❌ Чат-бот не инициализирован. Пожалуйста, перезапустите приложение."

        relevant_docs = self.find_relevant_docs(question)
        if not relevant_docs:
            return "❌ Информация не найдена. Попробуйте переформулировать вопрос или обновите данные."

        # Объединяем контекст из релевантных документов
        context = "\n\n".join([doc['content'] for doc in relevant_docs[:3]])

        # Ограничиваем контекст для производительности
        if len(context) > 1000:
            context = context[:1000]

        try:
            result = self.qa_pipeline(question=question, context=context)

            # Проверяем качество ответа
            if result['score'] < 0.1:
                return "❌ Не удалось найти точный ответ. Попробуйте переформулировать вопрос."

            sources = list(set([doc['source'] for doc in relevant_docs[:3]]))
            response = f"""**Ответ:** {result['answer']}

**Уверенность:** {result['score']:.1%}

**Источники:**
""" + "\n".join([f"• {src}" for src in sources])
            return response
        except Exception as e:
            return f"❌ Ошибка при обработке вопроса: {str(e)}"


class MUIvApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.parser_thread = None
        self.chatbot = MUIvChatBot()
        self.init_ui()
        self.apply_theme()
        self.check_data()

    def init_ui(self):
        self.setWindowTitle("🤖 МУИВ Чат-бот")
        self.setGeometry(100, 100, 1200, 600)
        self.setMinimumSize(800, 600)

        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QHBoxLayout(central_widget)

        # Сплиттер
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Левая панель - управление
        left_panel = QFrame()
        left_panel.setFixedWidth(300)
        left_layout = QVBoxLayout(left_panel)
        splitter.addWidget(left_panel)

        # Добавляем логотип из файла logo.jpg
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)

        # Загружаем логотип из файла logo.jpg
        logo_path = "logo.jpg"
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                # Масштабируем логотип до размера 150x150 пикселей
                pixmap = pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo_label.setPixmap(pixmap)
            else:
                # Если файл поврежден
                logo_label.setText("❌")
                logo_label.setStyleSheet("font-size: 48px; color: #8B0000;")
        else:
            # Если файл не найден
            logo_label.setText("🏛️")
            logo_label.setStyleSheet("font-size: 64px; color: #8B0000;")
            # Выводим предупреждение в лог
            print(f"Файл логотипа не найден: {logo_path}")

        left_layout.addWidget(logo_label)

        # Добавляем отступ после логотипа
        left_layout.addSpacing(5)

        # Заголовок
        title = QLabel("🏛️ Умный помощник")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin: 20px;")
        left_layout.addWidget(title)

        # Кнопка парсинга
        self.parse_btn = QPushButton("🔄 Спарсить данные")
        self.parse_btn.clicked.connect(self.start_parsing)
        left_layout.addWidget(self.parse_btn)

        # Прогресс бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        left_layout.addWidget(self.progress_bar)

        # Лог
        log_label = QLabel("📋 Лог работы:")
        left_layout.addWidget(log_label)

        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(200)
        self.log_text.setReadOnly(True)
        left_layout.addWidget(self.log_text)

        # Статус
        self.status_label = QLabel("⚠️ Загрузите данные для начала работы")
        left_layout.addWidget(self.status_label)

        left_layout.addStretch()

        # Правая панель - чат
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        splitter.addWidget(right_panel)

        # Чат область
        chat_label = QLabel("💬 Задайте интересующий вопрос")
        right_layout.addWidget(chat_label)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)

        # Проверяем наличие файла фона
        background_image_path = "fon.png"
        if os.path.exists(background_image_path):
            # Экранируем слеши для CSS
            bg_path = background_image_path.replace('\\', '/')
            self.chat_display.setStyleSheet(f"""
                QTextEdit {{
                    background: url({bg_path}) no-repeat center center;
                    background-size: cover;
                    border: 2px solid #e0e0e0;
                    border-radius: 10px;
                    padding: 15px;
                    font-size: 14px;
                    color: #000000;
                }}
            """)
        else:
            # Если файл фона не найден, используем обычный стиль
            self.chat_display.setStyleSheet("""
                QTextEdit {
                    background: white;
                    border: 2px solid #e0e0e0;
                    border-radius: 10px;
                    padding: 15px;
                    font-size: 14px;
                }
            """)
            # Выводим предупреждение
            print(f"Файл фона не найден: {background_image_path}")

        right_layout.addWidget(self.chat_display)

        # Ввод вопроса
        input_layout = QHBoxLayout()
        self.question_input = QLineEdit()
        self.question_input.setPlaceholderText("Введите ваш вопрос о МУИВ...")
        self.question_input.returnPressed.connect(self.send_question)
        input_layout.addWidget(self.question_input)

        send_btn = QPushButton("🚀 Спросить")
        send_btn.clicked.connect(self.send_question)
        input_layout.addWidget(send_btn)

        right_layout.addLayout(input_layout)

        # Растягиваем правую панель
        splitter.setStretchFactor(1, 2)

        # Примеры вопросов
        examples_frame = QFrame()
        examples_layout = QHBoxLayout(examples_frame)
        examples_label = QLabel("Примеры: ")
        examples_layout.addWidget(examples_label)

        example_questions = [
            "Какие документы нужны для поступления?",
            "Когда начинается учебный год?",
            "Как получить стипендию?"
        ]

        for eq in example_questions:
            btn = QPushButton(eq)
            btn.setMaximumHeight(30)
            btn.setStyleSheet("""
                QPushButton {
                    background: #f0f0f0;
                    color: #8B0000;
                    padding: 5px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background: #e0e0e0;
                }
            """)
            btn.clicked.connect(lambda checked, q=eq: self.set_example_question(q))
            examples_layout.addWidget(btn)

        right_layout.addWidget(examples_frame)

    def set_example_question(self, question):
        self.question_input.setText(question)
        self.send_question()

    def apply_theme(self):
        # Красно-белая палитра МУИВ
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(255, 255, 255))
        palette.setColor(QPalette.WindowText, QColor(139, 0, 0))
        palette.setColor(QPalette.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.AlternateBase, QColor(245, 245, 245))
        palette.setColor(QPalette.Text, QColor(50, 50, 50))
        palette.setColor(QPalette.Button, QColor(255, 255, 255))
        palette.setColor(QPalette.ButtonText, QColor(139, 0, 0))
        palette.setColor(QPalette.Highlight, QColor(139, 0, 0))
        palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        self.setPalette(palette)

        # Стили
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #FFFFFF, stop:1 #F8F8F8);
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #8B0000, stop:1 #A52A2A);
                color: white;
                border: none;
                padding: 12px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #A52A2A, stop:1 #B22222);
            }
            QPushButton:pressed {
                background: #7B0000;
            }
            QLineEdit {
                padding: 12px;
                border: 2px solid #ddd;
                border-radius: 8px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #8B0000;
            }
            QProgressBar {
                border: 2px solid #8B0000;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #8B0000, stop:1 #DC143C);
                border-radius: 3px;
            }
            QLabel {
                color: #8B0000;
                font-size: 14px;
                padding: 5px;
            }
        """)

    def log(self, message):
        self.log_text.append(f"[{time.strftime('%H:%M:%S')}] {message}")
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def check_data(self):
        if list(Path("muiv_data").glob("*.json")):
            self.load_chatbot()
        else:
            self.status_label.setText("⚠️ Данные не найдены. Нажмите 'Спарсить данные'")

    def load_chatbot(self):
        self.log("Загрузка чат-бота...")
        self.status_label.setText("🔄 Загрузка моделей...")
        QApplication.processEvents()

        if self.chatbot.load_model():
            doc_count = self.chatbot.load_documents()
            self.status_label.setText(f"✅ Готов к работе! Загружено {doc_count} документов")
            self.parse_btn.setText("🔄 Обновить данные")
            self.log("✅ Чат-бот готов!")

            # Приветственное сообщение
            welcome_msg = """**🤖 Добро пожаловать в чат-бота МУИВ!**

Я могу помочь вам с вопросами о:
- Поступлении в университет
- Учебном процессе
- Документах и требованиях
- Стипендиях и льготах

Задайте свой вопрос, и я постараюсь найти ответ на сайте МУИВ."""
            self.chat_display.append(welcome_msg)
            self.chat_display.append("-" * 80)
        else:
            self.status_label.setText("❌ Ошибка загрузки моделей")
            self.log("❌ Не удалось загрузить модели NLP")

    def start_parsing(self):
        self.parse_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.log("🚀 Начинаем парсинг сайта МУИВ...")

        self.parser_thread = ParserThread()
        self.parser_thread.progress.connect(self.progress_bar.setValue)
        self.parser_thread.finished.connect(self.on_parsing_finished)
        self.parser_thread.log_message.connect(self.log)
        self.parser_thread.start()

    def on_parsing_finished(self, data):
        self.progress_bar.setVisible(False)
        self.parse_btn.setEnabled(True)
        self.log(f"✅ Парсинг завершен! Обработано страниц: {len(data)}")
        self.load_chatbot()

    def send_question(self):
        question = self.question_input.text().strip()
        if not question:
            return

        self.chat_display.append(f"👤 **Вы:** {question}")
        self.question_input.clear()

        self.chat_display.append("🤖 **МУИВ-бот:** Думаю над ответом...")
        QApplication.processEvents()

        if not self.chatbot.qa_pipeline:
            self.chat_display.append("❌ Чат-бот не загружен. Нажмите 'Спарсить данные' для инициализации.")
            return

        answer = self.chatbot.answer_question(question)
        # Заменяем последнее сообщение на реальный ответ
        cursor = self.chat_display.textCursor()
        cursor.movePosition(cursor.End)
        cursor.movePosition(cursor.StartOfLine, cursor.KeepAnchor)
        cursor.removeSelectedText()
        cursor.deletePreviousChar()

        self.chat_display.append(answer)
        self.chat_display.append("-" * 80)


def main():
    app = QApplication(sys.argv)
    window = MUIvApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()