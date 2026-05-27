import sys
import json # чтение и запись пользовательских данных
import os
import re # регулярные выражения
import sqlite3 # реляционная база данных
import shutil # высокоуровневых операций с файлами
import csv #  чтение и запись
from datetime import datetime # датой и временем
# графический интерфейс
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QPushButton, QTextEdit, QLabel, QProgressBar, QLineEdit,
    QMessageBox, QSplitter, QFrame, QGroupBox, QDialog, QFormLayout,
    QDialogButtonBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QInputDialog, QComboBox, QTreeWidget, QTreeWidgetItem,
    QScrollArea, QListWidget, QListWidgetItem, QCheckBox, QFileDialog,
    QProgressDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt5.QtGui import QFont, QPalette, QColor, QPixmap, QIcon, QDesktopServices

# ========== WebEngine для просмотра файлов ==========
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False
    QWebEngineView = None

# ========== Для работы с моделью интентов ==========
try:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    torch = None


# ======================== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ (JSON) ========================
class UserManager:
    def __init__(self, users_file="users.json"):
        self.users_file = users_file
        self.users = self._load_users()

    def _load_users(self):
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        default_users = {
            "student": {"password": "student", "role": "student", "full_name": "Студент Петров", "email": "student@muiv.ru"},
            "admin": {"password": "admin", "role": "admin", "full_name": "Администратор", "email": "admin@muiv.ru"}
        }
        self._save_users(default_users)
        return default_users

    def _save_users(self, users_data=None):
        if users_data is None:
            users_data = self.users
        with open(self.users_file, 'w', encoding='utf-8') as f:
            json.dump(users_data, f, ensure_ascii=False, indent=2)

    def authenticate(self, username, password):
        user = self.users.get(username)
        if user and user.get("password") == password:
            return user.get("role")
        return None

    def register(self, username, password, role="student", full_name="", email=""):
        if not username or not password:
            return False, "Логин и пароль не могут быть пустыми"
        if username in self.users:
            return False, "Пользователь с таким логином уже существует"
        self.users[username] = {"password": password, "role": role, "full_name": full_name, "email": email}
        self._save_users()
        return True, "Регистрация успешна"

    def list_users(self):
        return [(name, data["role"], data.get("full_name", ""), data.get("email", "")) for name, data in self.users.items()]

    def delete_user(self, username):
        if username in self.users and username not in ("admin", "student"):
            del self.users[username]
            self._save_users()
            return True
        return False

    def change_role(self, username, new_role):
        if username in self.users and username not in ("admin", "student"):
            self.users[username]["role"] = new_role
            self._save_users()
            return True
        return False

    def get_user_info(self, username):
        return self.users.get(username)

    def get_user_by_id(self, user_id):
        for name, data in self.users.items():
            if name == user_id:
                return data
        return None


# ======================== КЛАССИФИКАТОР ИНТЕНТОВ (RuBERT) ========================
class IntentClassifier:
    def __init__(self, model_path="./rubert_intent_model_final"):
        self.model = None
        self.tokenizer = None
        self.labels = []
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu") if torch else "cpu"
        if TRANSFORMERS_AVAILABLE and os.path.exists(model_path):
            try:
                self.model = AutoModelForSequenceClassification.from_pretrained(model_path).to(self.device)
                self.tokenizer = AutoTokenizer.from_pretrained(model_path)
                if hasattr(self.model.config, 'id2label'):
                    self.labels = [self.model.config.id2label[i] for i in range(len(self.model.config.id2label))]
                else:
                    # стандартные метки (должны соответствовать обучению)
                    self.labels = ["greeting", "spo", "bachelor", "specialist", "cost", "duration",
                                   "admission", "documents", "schedule", "library", "unknown"]
                print(f"Модель загружена, устройство: {self.device}, меток: {len(self.labels)}")
            except Exception as e:
                print(f"Ошибка загрузки модели: {e}")
                self.model = None
        else:
            print("Модель не найдена или transformers недоступны, классификация интентов отключена")

    def predict(self, text, threshold=0.7):
        if self.model is None or self.tokenizer is None:
            return None, 0.0
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=128)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = torch.softmax(outputs.logits, dim=1)
            conf, pred = torch.max(probs, dim=1)
        conf = conf.item()
        if conf >= threshold:
            intent = self.labels[pred.item()] if pred.item() < len(self.labels) else "unknown"
            return intent, conf
        return None, conf


# ======================== БАЗА ДАННЫХ УНИВЕРСИТЕТА (JSON) ========================
class UniversityDatabase:
    def __init__(self):
        self.data_file = "university_data.json"
        self.data = {
            "spo": {"title": "Среднее профессиональное образование (колледж)", "specialties": [], "costs": {}},
            "bachelor": {"title": "Бакалавриат", "specialties": [], "costs": {}},
            "specialist": {"title": "Специалитет", "specialties": [], "costs": {}}
        }
        self.qa_pairs = []
        self._load_or_init_data()

    def _load_or_init_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    self.data = saved.get("data", self.data)
                    self.qa_pairs = saved.get("qa_pairs", [])
                    if not self.qa_pairs:
                        self._init_default_qa()
                return
            except:
                pass
        self._init_default_data()
        self._init_default_qa()
        self.save_to_file()

    def _init_default_data(self):
        # Примеры данных (для полноты)
        spo_specialties = [
            {"code": "38.02.07", "name": "Банковское дело", "qualification": "Специалист банковского дела",
             "duration_full_9": "2г 10м", "duration_full_11": "1г 10м", "form": "очная", "costs": {"full_9": 100000, "full_11": 110000}}
        ]
        self.data["spo"]["specialties"] = spo_specialties
        bachelor_specialties = [
            {"code": "38.03.01", "name": "Экономика", "profiles": ["Бизнес-аналитика"], "duration": "4 года", "form": "очная", "costs": {"full": 166000}}
        ]
        self.data["bachelor"]["specialties"] = bachelor_specialties
        self.data["specialist"]["specialties"] = []

    def _init_default_qa(self):
        self.qa_pairs = [
            {"keywords": ["привет", "здравствуй", "добрый день"], "answer": "Здравствуйте! Я - информационный помощник МУИВ."},
            {"keywords": ["кто ты", "ты кто"], "answer": "Я - виртуальный помощник Московского университета имени С.Ю. Витте."},
            {"keywords": ["спо", "колледж"], "answer": self._get_spo_overview},
            {"keywords": ["бакалавриат"], "answer": self._get_bachelor_overview},
            {"keywords": ["стоимость", "цена"], "answer": self._get_cost_info},
            {"keywords": ["срок", "длится"], "answer": self._get_duration_info},
            {"keywords": ["поступление", "документы"], "answer": "📄 Для поступления нужны аттестат, паспорт, фото, заявление."},
        ]

    def _get_spo_overview(self, query=""):
        return "СПО – среднее профессиональное образование, сроки от 1г 10м до 4г 4м."
    def _get_bachelor_overview(self, query=""):
        return "Бакалавриат – 4-5 лет, стоимость от 43 000 до 166 000 руб/семестр."
    def _get_cost_info(self, query=""):
        return "Стоимость: СПО от 50 000, бакалавриат от 43 000 до 166 000 руб/семестр."
    def _get_duration_info(self, query=""):
        return "Сроки: СПО 1-4 года, бакалавриат 4-5 лет, специалитет 5-6 лет."

    def save_to_file(self):
        safe_qa = []
        for qa in self.qa_pairs:
            ans = qa["answer"]
            if callable(ans):
                ans = ans("")
            safe_qa.append({"keywords": qa["keywords"], "answer": ans})
        to_save = {"data": self.data, "qa_pairs": safe_qa}
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(to_save, f, ensure_ascii=False, indent=2)

    def get_specialties(self, level):
        return self.data[level]["specialties"]

    def add_specialty(self, level, spec):
        self.data[level]["specialties"].append(spec)
        self.save_to_file()

    def update_specialty(self, level, index, spec):
        if 0 <= index < len(self.data[level]["specialties"]):
            self.data[level]["specialties"][index] = spec
            self.save_to_file()

    def delete_specialty(self, level, index):
        if 0 <= index < len(self.data[level]["specialties"]):
            self.data[level]["specialties"].pop(index)
            self.save_to_file()

    def get_qa_pairs(self):
        return self.qa_pairs

    def add_qa_pair(self, keywords, answer):
        self.qa_pairs.append({"keywords": keywords, "answer": answer})
        self.save_to_file()

    def update_qa_pair(self, index, keywords, answer):
        if 0 <= index < len(self.qa_pairs):
            self.qa_pairs[index] = {"keywords": keywords, "answer": answer}
            self.save_to_file()

    def delete_qa_pair(self, index):
        if 0 <= index < len(self.qa_pairs):
            self.qa_pairs.pop(index)
            self.save_to_file()

    def search(self, query):
        query_lower = query.lower()
        results = []
        for level_key in ["spo", "bachelor", "specialist"]:
            for spec in self.data[level_key]["specialties"]:
                if (query_lower in spec.get("name", "").lower() or
                    query_lower in spec.get("code", "").lower() or
                    query_lower in spec.get("qualification", "").lower()):
                    results.append((self.data[level_key]["title"], spec))
        return results


# ======================== SQLite АДМИН-БАЗА ========================
class AdminDatabase:
    def __init__(self, db_path="muiv_admin.db"):
        self.conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        self.cursor = self.conn.cursor()
        self._init_tables()
        self._import_csv_if_needed()

    def _init_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, url TEXT NOT NULL, data_type TEXT, category TEXT,
                last_updated TIMESTAMP, is_active INTEGER DEFAULT 1, update_frequency TEXT DEFAULT 'weekly'
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS update_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT, source_id INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, status TEXT,
                items_added INTEGER, error_message TEXT
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS academic_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT NOT NULL, filepath TEXT NOT NULL,
                category TEXT, uploaded_by INTEGER, uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                description TEXT
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT, question TEXT NOT NULL,
                answer TEXT, status TEXT DEFAULT 'open', assigned_to TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, resolved_at TIMESTAMP
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS faq_sqlite (
                id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT NOT NULL, answer TEXT NOT NULL,
                category TEXT, source_url TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def _import_csv_if_needed(self):
        self.cursor.execute("SELECT COUNT(*) FROM faq_sqlite")
        if self.cursor.fetchone()[0] == 0 and os.path.exists("university.csv"):
            with open("university.csv", 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    q = row.get("question", "").strip()
                    a = row.get("answer", "").strip()
                    if q and a:
                        self.cursor.execute('INSERT INTO faq_sqlite (question, answer, category) VALUES (?, ?, ?)',
                                            (q, a, "Импортированные вопросы"))
            self.conn.commit()
            print("FAQ импортирован из university.csv")

    # --- Источники данных ---
    def get_data_sources(self):
        self.cursor.execute("SELECT id, name, url, data_type, category, is_active, last_updated FROM data_sources")
        return self.cursor.fetchall()
    def add_data_source(self, name, url, data_type, category, update_frequency):
        self.cursor.execute('''INSERT INTO data_sources (name, url, data_type, category, update_frequency, last_updated, is_active)
                               VALUES (?, ?, ?, ?, ?, ?, 1)''', (name, url, data_type, category, update_frequency, datetime.now()))
        self.conn.commit()
        return self.cursor.lastrowid
    def update_data_source(self, source_id, name, url, data_type, category, update_frequency, is_active):
        self.cursor.execute('''UPDATE data_sources SET name=?, url=?, data_type=?, category=?, update_frequency=?, is_active=?
                               WHERE id=?''', (name, url, data_type, category, update_frequency, is_active, source_id))
        self.conn.commit()
    def delete_data_source(self, source_id):
        self.cursor.execute("DELETE FROM data_sources WHERE id=?", (source_id,))
        self.conn.commit()
    def set_last_updated(self, source_id):
        self.cursor.execute("UPDATE data_sources SET last_updated=? WHERE id=?", (datetime.now(), source_id))
        self.conn.commit()
    def log_update(self, source_id, status, items_added=0, error_message=None):
        self.cursor.execute("INSERT INTO update_log (source_id, status, items_added, error_message) VALUES (?, ?, ?, ?)",
                            (source_id, status, items_added, error_message))
        self.conn.commit()

    # --- Файлы ---
    def get_academic_files(self, category=None):
        if category:
            self.cursor.execute('''SELECT id, filename, filepath, category, description, uploaded_at
                                   FROM academic_files WHERE category=? ORDER BY uploaded_at DESC''', (category,))
        else:
            self.cursor.execute('''SELECT id, filename, filepath, category, description, uploaded_at
                                   FROM academic_files ORDER BY uploaded_at DESC''')
        return self.cursor.fetchall()
    def add_academic_file(self, filename, filepath, category, uploaded_by, description):
        self.cursor.execute('''INSERT INTO academic_files (filename, filepath, category, uploaded_by, description)
                               VALUES (?, ?, ?, ?, ?)''', (filename, filepath, category, uploaded_by, description))
        self.conn.commit()
        return self.cursor.lastrowid
    def delete_academic_file(self, file_id):
        self.cursor.execute("SELECT filepath FROM academic_files WHERE id=?", (file_id,))
        row = self.cursor.fetchone()
        if row and os.path.exists(row[0]):
            os.remove(row[0])
        self.cursor.execute("DELETE FROM academic_files WHERE id=?", (file_id,))
        self.conn.commit()
        return True

    # --- Настройки ---
    def get_setting(self, key, default=None):
        self.cursor.execute("SELECT value FROM bot_settings WHERE key=?", (key,))
        row = self.cursor.fetchone()
        return row[0] if row else default
    def set_setting(self, key, value):
        self.cursor.execute("INSERT OR REPLACE INTO bot_settings (key, value, updated_at) VALUES (?, ?, ?)",
                            (key, value, datetime.now()))
        self.conn.commit()

    # --- Вопросы студентов ---
    def create_student_question(self, student_id, question):
        self.cursor.execute("INSERT INTO student_questions (student_id, question, status) VALUES (?, ?, 'open')",
                            (student_id, question))
        self.conn.commit()
        return self.cursor.lastrowid
    def get_open_questions(self):
        self.cursor.execute("SELECT id, student_id, question, created_at, status FROM student_questions WHERE status='open' ORDER BY created_at")
        return self.cursor.fetchall()
    def answer_question(self, question_id, answer, assigned_to):
        self.cursor.execute('''UPDATE student_questions SET answer=?, assigned_to=?, status='resolved', resolved_at=?
                               WHERE id=?''', (answer, assigned_to, datetime.now(), question_id))
        self.conn.commit()

    # --- Поиск FAQ ---
    def search_faq(self, question):
        """
        Умный поиск по таблице faq_sqlite на основе совпадения значимых слов.
        Возвращает (question, answer, source_url) или None.
        """
        import re
        from collections import Counter

        # Нормализация: убираем пунктуацию, цифры, приводим к нижнему регистру, разбиваем на слова
        def normalize(text):
            text = text.lower()
            # оставляем только буквы и пробелы (убираем цифры, знаки препинания)
            text = re.sub(r'[^a-zа-яё\s]', '', text)
            # убираем очень короткие слова (1-2 буквы), они неинформативны
            words = [w for w in text.split() if len(w) > 2]
            return words

        query_words = normalize(question)
        if not query_words:
            return None

        # Получаем все записи из FAQ
        self.cursor.execute("SELECT id, question, answer, source_url FROM faq_sqlite")
        all_rows = self.cursor.fetchall()

        best_match = None
        best_score = 0
        best_question = ""
        best_answer = ""
        best_url = None

        for fid, q_text, a_text, url in all_rows:
            db_words = normalize(q_text)
            if not db_words:
                continue
            # Количество общих слов
            common = set(query_words) & set(db_words)
            score = len(common)
            # Если совпадает хотя бы 2 слова ИЛИ доля совпадений > 30% от длины запроса
            if score >= max(2, len(query_words) * 0.3):
                if score > best_score:
                    best_score = score
                    best_match = fid
                    best_question = q_text
                    best_answer = a_text
                    best_url = url

        if best_match:
            return (best_question, best_answer, best_url)
        return None


# ======================== ПОТОК ДЛЯ ПАРСИНГА ========================
class ParserThread(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)
    def __init__(self, url, data_type):
        super().__init__()
        self.url = url
        self.data_type = data_type
    def run(self):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            resp = requests.get(self.url, headers=headers, timeout=30)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                if self.data_type == 'faq':
                    result = self._parse_faq(soup)
                elif self.data_type == 'prices':
                    result = self._parse_prices(soup)
                elif self.data_type == 'news':
                    result = self._parse_news(soup)
                else:
                    result = {'text': soup.get_text()[:5000]}
                self.finished.emit(result)
            else:
                self.error.emit(f"HTTP {resp.status_code}")
        except Exception as e:
            self.error.emit(str(e))
    def _parse_faq(self, soup):
        faqs = []
        for block in soup.find_all(['div', 'section'], class_=re.compile(r'faq|question|answer', re.I)):
            q = block.find(['h3', 'h4', 'div'], class_=re.compile(r'question|title', re.I))
            a = block.find(['div', 'p'], class_=re.compile(r'answer|content|text', re.I))
            if q and a:
                faqs.append({'question': q.get_text(strip=True), 'answer': a.get_text(strip=True)})
        return {'faqs': faqs}
    def _parse_prices(self, soup):
        prices = []
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all('td')
                if cells:
                    prices.append([c.get_text(strip=True) for c in cells])
        return {'prices': prices}
    def _parse_news(self, soup):
        news = []
        for block in soup.find_all(['article', 'div'], class_=re.compile(r'news|post', re.I))[:10]:
            title = block.find(['h2', 'h3', 'h4'])
            date = block.find(['time', 'span'], class_=re.compile(r'date', re.I))
            content = block.find(['p', 'div'], class_=re.compile(r'content|excerpt', re.I))
            news.append({
                'title': title.get_text(strip=True) if title else 'Новость',
                'date': date.get_text(strip=True) if date else '',
                'content': content.get_text(strip=True)[:500] if content else ''
            })
        return {'news': news}


# ======================== ЧАТ-БОТ (расширенный с моделью интентов) ========================
class MUIvChatBot:
    def __init__(self, json_db, admin_db, user_manager):
        self.json_db = json_db
        self.admin_db = admin_db
        self.user_manager = user_manager
        self.intent_classifier = IntentClassifier()
        self.intent_threshold = float(self.admin_db.get_setting("intent_threshold", "0.7"))

    # ----- Обработчики интентов -----
    def _handle_greeting(self, text):
        return "Здравствуйте! Я помощник МУИВ. Спросите о специальностях, стоимости или поступлении."

    def _handle_spo(self, text):
        return self.json_db._get_spo_overview(text)

    def _handle_bachelor(self, text):
        return self.json_db._get_bachelor_overview(text)

    def _handle_specialist(self, text):
        return "Специалитет – программы 5-6 лет, углублённая подготовка."

    def _handle_cost(self, text):
        return self.json_db._get_cost_info(text)

    def _handle_duration(self, text):
        return self.json_db._get_duration_info(text)

    def _handle_admission(self, text):
        return "Поступление: аттестат/диплом, паспорт, заявление, фото, результаты ЕГЭ (для бакалавриата/специалитета)."

    def _handle_documents(self, text):
        return "Документы: паспорт, аттестат (или диплом), 4 фото, заявление, СНИЛС (при наличии)."

    def _handle_schedule(self, text):
        return "Расписание занятий доступно в разделе 'Академические файлы' у администратора."

    def _handle_library(self, text):
        return "Электронная библиотека: https://muiv.ru/elibrary"

    def _handle_unknown(self, text):
        return None

    def answer_question(self, question, student_id=None):
        # 1. Умный поиск в SQLite FAQ (самый надёжный источник)
        faq_row = self.admin_db.search_faq(question)
        if faq_row:
            q_text, a_text, url = faq_row
            return f"📘 {a_text}\n(Источник: {url or 'база знаний МУИВ'})"

        # 2. Классификация интентов (если модель загружена)
        if self.intent_classifier.model is not None:
            intent, conf = self.intent_classifier.predict(question, threshold=self.intent_threshold)
            if intent and intent != "unknown":
                handler = getattr(self, f"_handle_{intent}", None)
                if handler:
                    answer = handler(question)
                    if answer:
                        return answer

        # 3. Поиск по статическим QA-парам (JSON)
        q_lower = question.lower()
        for qa in self.json_db.qa_pairs:
            for kw in qa["keywords"]:
                if kw in q_lower:
                    ans = qa["answer"]
                    if callable(ans):
                        return ans(question)
                    return ans

        # 4. Поиск по специальностям (JSON)
        res = self.json_db.search(q_lower)
        if res:
            answer = "🔍 Найдено в специальностях:\n"
            for level, spec in res[:3]:
                answer += f"**{level}**: {spec['code']} {spec['name']}\n"
            return answer

        # 5. Интернет-поиск (если включён)
        if self.admin_db.get_setting("academic_online_enabled", "true") == "true":
            success, answer = self.search_online(question)
            if success:
                return f"🌐 {answer}"

        # 6. Создание тикета (только для студентов)
        if student_id:
            ticket_id = self.admin_db.create_student_question(student_id, question)
            return f"❓ Ответ не найден. Ваш вопрос передан в поддержку (№{ticket_id})."

        return "❓ Не понял вопрос. Пожалуйста, уточните или обратитесь в приёмную комиссию."
    def search_online(self, question):
        success, answer = False, ""
        try:
            url = "https://api.duckduckgo.com/"
            params = {'q': question, 'format': 'json', 'no_html': 1}
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('AbstractText'):
                    answer = data['AbstractText']
                    success = True
                elif data.get('RelatedTopics'):
                    first = data['RelatedTopics'][0]
                    if 'Text' in first:
                        answer = first['Text']
                        success = True
        except:
            pass
        return success, answer


# ======================== АДМИН-ВИДЖЕТЫ ========================
class AdminDataSourcesWidget(QWidget):
    def __init__(self, admin_db):
        super().__init__()
        self.admin_db = admin_db
        self.init_ui()
        self.load_sources()
    def init_ui(self):
        layout = QVBoxLayout(self)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["ID", "Название", "URL", "Тип", "Категория", "Активен", "Обновлено"])
        layout.addWidget(self.tree)
        btn_layout = QHBoxLayout()
        for text, func in [("➕ Добавить", self.add_source), ("✏️ Редактировать", self.edit_source),
                           ("🗑️ Удалить", self.delete_source), ("🔄 Обновить", self.update_source)]:
            btn = QPushButton(text)
            btn.clicked.connect(func)
            btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)
        refresh_btn = QPushButton("Обновить список")
        refresh_btn.clicked.connect(self.load_sources)
        layout.addWidget(refresh_btn)
    def load_sources(self):
        self.tree.clear()
        for row in self.admin_db.get_data_sources():
            id_, name, url, dt, cat, active, updated = row
            active_str = "✅" if active else "❌"
            updated_str = str(updated)[:19] if updated else "никогда"
            self.tree.addTopLevelItem(QTreeWidgetItem([str(id_), name, url[:50], dt, cat, active_str, updated_str]))
    def add_source(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Добавить источник")
        layout = QFormLayout(dialog)
        name_ed = QLineEdit()
        url_ed = QLineEdit()
        type_cb = QComboBox()
        type_cb.addItems(["faq", "prices", "news", "general"])
        cat_cb = QComboBox()
        cat_cb.addItems(["Общие", "Стоимость обучения", "Поступление", "Новости"])
        freq_cb = QComboBox()
        freq_cb.addItems(["daily", "weekly", "monthly"])
        layout.addRow("Название:", name_ed)
        layout.addRow("URL:", url_ed)
        layout.addRow("Тип данных:", type_cb)
        layout.addRow("Категория:", cat_cb)
        layout.addRow("Частота:", freq_cb)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)
        if dialog.exec_() == QDialog.Accepted and name_ed.text() and url_ed.text():
            self.admin_db.add_data_source(name_ed.text(), url_ed.text(), type_cb.currentText(),
                                          cat_cb.currentText(), freq_cb.currentText())
            self.load_sources()
    def edit_source(self):
        sel = self.tree.selectedItems()
        if not sel:
            QMessageBox.warning(self, "Ошибка", "Выберите источник")
            return
        sid = int(sel[0].text(0))
        self.admin_db.cursor.execute("SELECT name, url, data_type, category, update_frequency, is_active FROM data_sources WHERE id=?", (sid,))
        row = self.admin_db.cursor.fetchone()
        if not row:
            return
        name, url, dt, cat, freq, active = row
        dialog = QDialog(self)
        dialog.setWindowTitle("Редактировать источник")
        layout = QFormLayout(dialog)
        name_ed = QLineEdit(name)
        url_ed = QLineEdit(url)
        type_cb = QComboBox()
        type_cb.addItems(["faq", "prices", "news", "general"])
        type_cb.setCurrentText(dt)
        cat_cb = QComboBox()
        cat_cb.addItems(["Общие", "Стоимость обучения", "Поступление", "Новости"])
        cat_cb.setCurrentText(cat)
        freq_cb = QComboBox()
        freq_cb.addItems(["daily", "weekly", "monthly"])
        freq_cb.setCurrentText(freq)
        active_cb = QCheckBox("Активен")
        active_cb.setChecked(active == 1)
        layout.addRow("Название:", name_ed)
        layout.addRow("URL:", url_ed)
        layout.addRow("Тип:", type_cb)
        layout.addRow("Категория:", cat_cb)
        layout.addRow("Частота:", freq_cb)
        layout.addRow(active_cb)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)
        if dialog.exec_() == QDialog.Accepted:
            self.admin_db.update_data_source(sid, name_ed.text(), url_ed.text(), type_cb.currentText(),
                                             cat_cb.currentText(), freq_cb.currentText(), 1 if active_cb.isChecked() else 0)
            self.load_sources()
    def delete_source(self):
        sel = self.tree.selectedItems()
        if sel and QMessageBox.question(self, "Удаление", "Удалить источник?") == QMessageBox.Yes:
            self.admin_db.delete_data_source(int(sel[0].text(0)))
            self.load_sources()
    def update_source(self):
        sel = self.tree.selectedItems()
        if not sel:
            return
        sid = int(sel[0].text(0))
        self.admin_db.cursor.execute("SELECT name, url, data_type, category FROM data_sources WHERE id=?", (sid,))
        row = self.admin_db.cursor.fetchone()
        if not row:
            return
        name, url, dt, cat = row
        self.thread = ParserThread(url, dt)
        self.progress = QProgressDialog(f"Обновление {name}...", "Отмена", 0, 100, self)
        self.progress.setWindowModality(Qt.WindowModal)
        self.thread.progress.connect(self.progress.setValue)
        self.thread.finished.connect(lambda data: self._process_data(sid, data, cat))
        self.thread.error.connect(lambda err: self._on_error(sid, err))
        self.thread.start()
    def _process_data(self, sid, data, category):
        added = 0
        if 'faqs' in data:
            for faq in data['faqs']:
                self.admin_db.cursor.execute('INSERT INTO faq_sqlite (question, answer, category, source_url) VALUES (?, ?, ?, ?)',
                                             (faq['question'], faq['answer'], category, self._get_source_url(sid)))
                added += 1
        elif 'prices' in data:
            for row in data['prices']:
                if len(row) >= 2:
                    q = f"Информация о стоимости: {row[0]}"
                    a = f"Стоимость: {' '.join(row[1:])}"
                    self.admin_db.cursor.execute('INSERT INTO faq_sqlite (question, answer, category, source_url) VALUES (?, ?, ?, ?)',
                                                 (q, a, category, self._get_source_url(sid)))
                    added += 1
        elif 'news' in data:
            for news in data['news']:
                q = f"Новость: {news['title']}"
                a = f"{news['date']}\n{news['content']}"
                self.admin_db.cursor.execute('INSERT INTO faq_sqlite (question, answer, category, source_url) VALUES (?, ?, ?, ?)',
                                             (q, a, category, self._get_source_url(sid)))
                added += 1
        self.admin_db.conn.commit()
        self.admin_db.set_last_updated(sid)
        self.admin_db.log_update(sid, 'success', added)
        QMessageBox.information(self, "Готово", f"Добавлено {added} записей")
    def _get_source_url(self, sid):
        self.admin_db.cursor.execute("SELECT url FROM data_sources WHERE id=?", (sid,))
        row = self.admin_db.cursor.fetchone()
        return row[0] if row else None
    def _on_error(self, sid, err):
        self.admin_db.log_update(sid, 'error', error_message=err)
        QMessageBox.warning(self, "Ошибка", f"Не удалось обновить: {err}")

class AdminAcademicFilesWidget(QWidget):
    def __init__(self, admin_db, parent_app):
        super().__init__()
        self.admin_db = admin_db
        self.parent_app = parent_app
        self.init_ui()
        self.load_files()
    def init_ui(self):
        layout = QVBoxLayout(self)
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.SingleSelection)
        layout.addWidget(self.file_list)
        btn_layout = QHBoxLayout()
        for text, func in [("📤 Загрузить", self.upload_file), ("🗑️ Удалить", self.delete_file), ("👁️ Просмотреть", self.open_file)]:
            btn = QPushButton(text)
            btn.clicked.connect(func)
            btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)
        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.load_files)
        layout.addWidget(refresh_btn)
    def load_files(self):
        self.file_list.clear()
        for fid, fname, fpath, cat, desc, dt in self.admin_db.get_academic_files():
            text = f"{fname} [{cat}]" + (f" - {desc}" if desc else "")
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, (fid, fpath, fname))
            self.file_list.addItem(item)
    def upload_file(self):
        fpath, _ = QFileDialog.getOpenFileName(self, "Выберите файл", "", "Все файлы (*.*)")
        if not fpath:
            return
        cat, ok = QInputDialog.getText(self, "Категория", "Категория (например, Расписание):")
        if not ok:
            return
        desc, ok = QInputDialog.getText(self, "Описание", "Описание (необязательно):")
        if not ok:
            desc = ""
        filename = os.path.basename(fpath)
        dest_dir = "academic_files"
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, filename)
        if os.path.exists(dest):
            name, ext = os.path.splitext(filename)
            filename = f"{name}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
            dest = os.path.join(dest_dir, filename)
        shutil.copy2(fpath, dest)
        self.admin_db.add_academic_file(filename, dest, cat, 0, desc)
        self.load_files()
        QMessageBox.information(self, "Успех", f"Файл {filename} загружен")
    def delete_file(self):
        item = self.file_list.currentItem()
        if not item:
            return
        fid, fpath, fname = item.data(Qt.UserRole)
        if QMessageBox.question(self, "Удаление", f"Удалить {fname}?") == QMessageBox.Yes:
            self.admin_db.delete_academic_file(fid)
            self.load_files()
    def open_file(self):
        item = self.file_list.currentItem()
        if not item:
            return
        fid, fpath, fname = item.data(Qt.UserRole)
        if not os.path.exists(fpath):
            QMessageBox.warning(self, "Ошибка", "Файл не найден")
            return
        ext = os.path.splitext(fname)[1].lower()
        if WEBENGINE_AVAILABLE and QWebEngineView is not None:
            viewer = QDialog(self)
            viewer.setWindowTitle(f"Просмотр: {fname}")
            viewer.resize(900, 700)
            lay = QVBoxLayout(viewer)
            if ext in ['.pdf', '.txt', '.html', '.htm', '.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                web = QWebEngineView()
                web.load(QUrl.fromLocalFile(fpath))
                lay.addWidget(web)
            elif ext in ['.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']:
                file_url = QUrl.fromLocalFile(fpath).toString()
                google_url = f"https://docs.google.com/gview?embedded=true&url={file_url}"
                web = QWebEngineView()
                web.load(QUrl(google_url))
                lay.addWidget(web)
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(fpath))
                viewer.close()
                return
            close_btn = QPushButton("Закрыть")
            close_btn.clicked.connect(viewer.accept)
            lay.addWidget(close_btn)
            viewer.exec()
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(fpath))

class AdminBotSettingsWidget(QWidget):
    def __init__(self, admin_db):
        super().__init__()
        self.admin_db = admin_db
        self.init_ui()
    def init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.welcome_edit = QTextEdit()
        self.welcome_edit.setPlainText(self.admin_db.get_setting("academic_welcome", "Добро пожаловать в раздел академических вопросов!"))
        form.addRow("Приветствие:", self.welcome_edit)
        self.search_local = QCheckBox("Искать в локальной базе")
        self.search_local.setChecked(self.admin_db.get_setting("academic_search_enabled", "true") == "true")
        self.search_online = QCheckBox("Искать в интернете")
        self.search_online.setChecked(self.admin_db.get_setting("academic_online_enabled", "true") == "true")
        form.addRow(self.search_local)
        form.addRow(self.search_online)
        # Настройка порога уверенности интента
        self.threshold_edit = QLineEdit()
        self.threshold_edit.setText(self.admin_db.get_setting("intent_threshold", "0.7"))
        form.addRow("Порог уверенности интента (0..1):", self.threshold_edit)
        layout.addLayout(form)
        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self.save)
        layout.addWidget(save_btn)
    def save(self):
        self.admin_db.set_setting("academic_welcome", self.welcome_edit.toPlainText())
        self.admin_db.set_setting("academic_search_enabled", "true" if self.search_local.isChecked() else "false")
        self.admin_db.set_setting("academic_online_enabled", "true" if self.search_online.isChecked() else "false")
        self.admin_db.set_setting("intent_threshold", self.threshold_edit.text())
        QMessageBox.information(self, "Сохранено", "Настройки обновлены")

class AdminStatsWidget(QWidget):
    def __init__(self, admin_db, user_manager):
        super().__init__()
        self.admin_db = admin_db
        self.user_manager = user_manager
        self.init_ui()
        self.load_stats()
    def init_ui(self):
        layout = QVBoxLayout(self)
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        layout.addWidget(self.stats_text)
        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.load_stats)
        layout.addWidget(refresh_btn)
    def load_stats(self):
        users = self.user_manager.list_users()
        roles = {'admin':0,'student':0}
        for _,role,_,_ in users:
            roles[role] = roles.get(role,0)+1
        self.admin_db.cursor.execute("SELECT COUNT(*) FROM faq_sqlite")
        faq_cnt = self.admin_db.cursor.fetchone()[0]
        self.admin_db.cursor.execute("SELECT COUNT(*) FROM data_sources WHERE is_active=1")
        src_cnt = self.admin_db.cursor.fetchone()[0]
        self.admin_db.cursor.execute("SELECT COUNT(*) FROM academic_files")
        files_cnt = self.admin_db.cursor.fetchone()[0]
        self.admin_db.cursor.execute("SELECT COUNT(*) FROM student_questions WHERE status='open'")
        open_q = self.admin_db.cursor.fetchone()[0]
        stats = f"""
📊 СТАТИСТИКА МУИВ

👥 Пользователи:
   Администраторы: {roles['admin']}
   Студенты: {roles['student']}

📚 База знаний:
   Всего вопросов в FAQ (SQLite): {faq_cnt}
   Активных источников: {src_cnt}

📁 Академические файлы: {files_cnt}

❓ Открытых вопросов студентов: {open_q}
        """
        self.stats_text.setText(stats)


# ======================== ОСНОВНЫЕ АДМИНСКИЕ ТАБЛИЦЫ ========================
class AdminSpecialtiesTable(QWidget):
    def __init__(self, db, level, parent=None):
        super().__init__(parent)
        self.db = db
        self.level = level
        self.init_ui()
        self.load_data()
    def init_ui(self):
        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("➕ Добавить")
        add_btn.clicked.connect(self.add_row)
        delete_btn = QPushButton("🗑️ Удалить")
        delete_btn.clicked.connect(self.delete_row)
        save_btn = QPushButton("💾 Сохранить")
        save_btn.clicked.connect(self.save_changes)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)
    def load_data(self):
        specs = self.db.get_specialties(self.level)
        if not specs:
            self.table.setRowCount(0)
            return
        if self.level == "spo":
            headers = ["Код", "Название", "Квалификация", "Срок (9кл)", "Срок (11кл)", "Форма"]
        else:
            headers = ["Код", "Название", "Профили", "Длительность", "Форма"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(specs))
        for row, spec in enumerate(specs):
            if self.level == "spo":
                self.table.setItem(row, 0, QTableWidgetItem(spec.get("code", "")))
                self.table.setItem(row, 1, QTableWidgetItem(spec.get("name", "")))
                self.table.setItem(row, 2, QTableWidgetItem(spec.get("qualification", "")))
                self.table.setItem(row, 3, QTableWidgetItem(spec.get("duration_full_9", "")))
                self.table.setItem(row, 4, QTableWidgetItem(spec.get("duration_full_11", "")))
                self.table.setItem(row, 5, QTableWidgetItem(spec.get("form", "")))
            else:
                self.table.setItem(row, 0, QTableWidgetItem(spec.get("code", "")))
                self.table.setItem(row, 1, QTableWidgetItem(spec.get("name", "")))
                profiles = ", ".join(spec.get("profiles", []))
                self.table.setItem(row, 2, QTableWidgetItem(profiles))
                self.table.setItem(row, 3, QTableWidgetItem(spec.get("duration", "")))
                self.table.setItem(row, 4, QTableWidgetItem(spec.get("form", "")))
        self.table.resizeColumnsToContents()
    def add_row(self):
        if self.level == "spo":
            spec = {"code": "00.00.00", "name": "Новая спец.", "qualification": "Новая", "duration_full_9": "",
                    "duration_full_11": "", "form": "очная", "costs": {}}
        else:
            spec = {"code": "00.00.00", "name": "Новое напр.", "profiles": [], "duration": "4 года", "form": "очная",
                    "costs": {}}
        self.db.add_specialty(self.level, spec)
        self.load_data()
    def delete_row(self):
        row = self.table.currentRow()
        if row >= 0:
            self.db.delete_specialty(self.level, row)
            self.load_data()
    def save_changes(self):
        specs = self.db.get_specialties(self.level)
        for row in range(self.table.rowCount()):
            if self.level == "spo":
                spec = {
                    "code": self.table.item(row, 0).text(),
                    "name": self.table.item(row, 1).text(),
                    "qualification": self.table.item(row, 2).text(),
                    "duration_full_9": self.table.item(row, 3).text(),
                    "duration_full_11": self.table.item(row, 4).text(),
                    "form": self.table.item(row, 5).text(),
                    "costs": specs[row].get("costs", {})
                }
            else:
                profiles_text = self.table.item(row, 2).text()
                profiles = [p.strip() for p in profiles_text.split(",") if p.strip()]
                spec = {
                    "code": self.table.item(row, 0).text(),
                    "name": self.table.item(row, 1).text(),
                    "profiles": profiles,
                    "duration": self.table.item(row, 3).text(),
                    "form": self.table.item(row, 4).text(),
                    "costs": specs[row].get("costs", {})
                }
            self.db.update_specialty(self.level, row, spec)
        QMessageBox.information(self, "Сохранено", "Изменения сохранены")

class AdminQATable(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.init_ui()
        self.load_data()
    def init_ui(self):
        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Ключевые слова", "Ответ"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("➕ Добавить")
        add_btn.clicked.connect(self.add_pair)
        delete_btn = QPushButton("🗑️ Удалить")
        delete_btn.clicked.connect(self.delete_pair)
        save_btn = QPushButton("💾 Сохранить")
        save_btn.clicked.connect(self.save_changes)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)
    def load_data(self):
        pairs = self.db.get_qa_pairs()
        self.table.setRowCount(len(pairs))
        for i, p in enumerate(pairs):
            keywords = ", ".join(p["keywords"])
            self.table.setItem(i, 0, QTableWidgetItem(keywords))
            ans = p["answer"] if isinstance(p["answer"], str) else "Функция"
            self.table.setItem(i, 1, QTableWidgetItem(ans))
        self.table.resizeColumnsToContents()
    def add_pair(self):
        kw, ok = QInputDialog.getText(self, "Новый QA", "Ключевые слова (через запятую):")
        if not ok: return
        keywords = [k.strip() for k in kw.split(",")]
        answer, ok = QInputDialog.getText(self, "Новый QA", "Ответ:")
        if not ok: return
        self.db.add_qa_pair(keywords, answer)
        self.load_data()
    def delete_pair(self):
        row = self.table.currentRow()
        if row >= 0:
            self.db.delete_qa_pair(row)
            self.load_data()
    def save_changes(self):
        for row in range(self.table.rowCount()):
            kw_str = self.table.item(row, 0).text()
            keywords = [k.strip() for k in kw_str.split(",")]
            answer = self.table.item(row, 1).text()
            self.db.update_qa_pair(row, keywords, answer)
        QMessageBox.information(self, "Сохранено", "QA обновлены")

class AdminUsersTable(QWidget):
    def __init__(self, user_manager, parent=None):
        super().__init__(parent)
        self.user_manager = user_manager
        self.init_ui()
        self.load_data()
    def init_ui(self):
        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Логин", "Роль", "Полное имя", "Email"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)
        btn_layout = QHBoxLayout()
        delete_btn = QPushButton("🗑️ Удалить")
        delete_btn.clicked.connect(self.delete_user)
        change_role_btn = QPushButton("👑 Изменить роль")
        change_role_btn.clicked.connect(self.change_role_dialog)
        btn_layout.addWidget(delete_btn)
        btn_layout.addWidget(change_role_btn)
        layout.addLayout(btn_layout)
    def load_data(self):
        users = self.user_manager.list_users()
        self.table.setRowCount(len(users))
        for i, (name, role, full_name, email) in enumerate(users):
            self.table.setItem(i, 0, QTableWidgetItem(name))
            self.table.setItem(i, 1, QTableWidgetItem(role))
            self.table.setItem(i, 2, QTableWidgetItem(full_name))
            self.table.setItem(i, 3, QTableWidgetItem(email))
        self.table.resizeColumnsToContents()
    def delete_user(self):
        row = self.table.currentRow()
        if row >= 0:
            username = self.table.item(row, 0).text()
            if username in ("admin", "student"):
                QMessageBox.warning(self, "Ошибка", "Нельзя удалить встроенного пользователя")
                return
            if self.user_manager.delete_user(username):
                self.load_data()
                QMessageBox.information(self, "Успех", f"Пользователь {username} удалён")
            else:
                QMessageBox.warning(self, "Ошибка", "Не удалось удалить")
    def change_role_dialog(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите пользователя!")
            return
        username = self.table.item(row, 0).text()
        if username in ("admin", "student"):
            QMessageBox.warning(self, "Ошибка", "Нельзя менять роль встроенного пользователя")
            return
        current_role = self.table.item(row, 1).text()
        dialog = QDialog(self)
        dialog.setWindowTitle("Смена роли")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"Пользователь: {username}"))
        combo = QComboBox()
        combo.addItems(["student", "admin"])
        combo.setCurrentText(current_role)
        layout.addWidget(combo)
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)
        if dialog.exec_() == QDialog.Accepted:
            new_role = combo.currentText()
            if self.user_manager.change_role(username, new_role):
                self.load_data()
                QMessageBox.information(self, "Успех", f"Роль {username} изменена на {new_role}")
            else:
                QMessageBox.warning(self, "Ошибка", "Не удалось изменить роль")


# ======================== ОКНО АВТОРИЗАЦИИ И РЕГИСТРАЦИИ ========================
class LoginWindow(QDialog):
    def __init__(self, user_manager, parent=None):
        super().__init__(parent)
        self.user_manager = user_manager
        self.user_role = None
        self.setWindowTitle("Вход в систему МУИВ")
        self.setFixedSize(500, 500)
        self.apply_theme()
        self.setup_ui()
    def apply_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(255,255,255))
        palette.setColor(QPalette.WindowText, QColor(139,0,0))
        palette.setColor(QPalette.Base, QColor(255,255,255))
        palette.setColor(QPalette.Button, QColor(255,255,255))
        palette.setColor(QPalette.ButtonText, QColor(139,0,0))
        palette.setColor(QPalette.Highlight, QColor(139,0,0))
        self.setPalette(palette)
        self.setStyleSheet("""
            QDialog { background: white; }
            QPushButton { background: #8B0000; color: white; border: none; padding: 12px; border-radius: 8px; font-weight: bold; }
            QPushButton:hover { background: #A52A2A; }
            QLineEdit { padding: 10px; border: 2px solid #ddd; border-radius: 8px; }
            QLineEdit:focus { border-color: #8B0000; }
            QLabel { color: #8B0000; }
        """)
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        if os.path.exists("logo.jpg"):
            pix = QPixmap("logo.jpg")
            if not pix.isNull():
                pix = pix.scaled(120,120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo_label.setPixmap(pix)
            else:
                logo_label.setText("🏛️")
                logo_label.setStyleSheet("font-size:48px;")
        else:
            logo_label.setText("🏛️")
            logo_label.setStyleSheet("font-size:48px;")
        layout.addWidget(logo_label)
        title = QLabel("Московский университет\nимени С.Ю. Витте")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:20px; font-weight:bold; margin:20px;")
        layout.addWidget(title)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Имя пользователя")
        layout.addWidget(self.username_input)
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Пароль")
        self.password_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password_input)
        btn_login = QPushButton("Войти")
        btn_login.clicked.connect(self.login)
        layout.addWidget(btn_login)
        btn_register = QPushButton("Регистрация")
        btn_register.clicked.connect(self.show_register)
        layout.addWidget(btn_register)
        info = QLabel("Тестовые учётные записи:\nstudent/student (студент)\nadmin/admin (администратор)")
        info.setAlignment(Qt.AlignCenter)
        info.setStyleSheet("color:#666; font-size:12px; margin-top:20px;")
        layout.addWidget(info)
    def login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        if not username or not password:
            QMessageBox.warning(self, "Ошибка", "Заполните все поля!")
            return
        role = self.user_manager.authenticate(username, password)
        if role:
            self.user_role = role
            self.accept()
        else:
            QMessageBox.warning(self, "Ошибка", "Неверное имя пользователя или пароль!")
    def show_register(self):
        reg = RegisterDialog(self.user_manager, self)
        reg.exec_()

class RegisterDialog(QDialog):
    def __init__(self, user_manager, parent=None):
        super().__init__(parent)
        self.user_manager = user_manager
        self.setWindowTitle("Регистрация")
        self.setFixedSize(450, 520)
        self.setup_ui()
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        title = QLabel("Регистрация нового пользователя")
        title.setStyleSheet("font-size:18px; font-weight:bold; color:#8B0000;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        form_layout = QFormLayout()
        self.username_edit = QLineEdit()
        self.fullname_edit = QLineEdit()
        self.email_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.confirm_edit = QLineEdit()
        self.confirm_edit.setEchoMode(QLineEdit.Password)
        self.role_combo = QComboBox()
        self.role_combo.addItems(["Студент"])
        form_layout.addRow("Имя пользователя:", self.username_edit)
        form_layout.addRow("Полное имя:", self.fullname_edit)
        form_layout.addRow("Email:", self.email_edit)
        form_layout.addRow("Пароль:", self.password_edit)
        form_layout.addRow("Подтвердите пароль:", self.confirm_edit)
        form_layout.addRow("Статус:", self.role_combo)
        layout.addLayout(form_layout)
        btn_register = QPushButton("Зарегистрироваться")
        btn_register.clicked.connect(self.register)
        layout.addWidget(btn_register)
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        layout.addWidget(btn_cancel)
    def register(self):
        username = self.username_edit.text().strip()
        fullname = self.fullname_edit.text().strip()
        email = self.email_edit.text().strip()
        password = self.password_edit.text().strip()
        confirm = self.confirm_edit.text().strip()
        role = "student"
        if not all([username, fullname, email, password, confirm]):
            QMessageBox.warning(self, "Ошибка", "Заполните все поля!")
            return
        if password != confirm:
            QMessageBox.warning(self, "Ошибка", "Пароли не совпадают!")
            return
        if username in self.user_manager.users:
            QMessageBox.warning(self, "Ошибка", "Пользователь с таким логином уже существует!")
            return
        ok, msg = self.user_manager.register(username, password, role, fullname, email)
        if ok:
            QMessageBox.information(self, "Успех", "Регистрация прошла успешно! Теперь вы можете войти.")
            self.accept()
        else:
            QMessageBox.warning(self, "Ошибка", msg)


# ======================== ГЛАВНОЕ ОКНО ПРИЛОЖЕНИЯ ========================
class MUIvApp(QMainWindow):
    def __init__(self, user_role, user_manager, json_db, admin_db):
        super().__init__()
        self.user_role = user_role
        self.user_manager = user_manager
        self.json_db = json_db
        self.admin_db = admin_db
        self.chatbot = MUIvChatBot(json_db, admin_db, user_manager)
        self.init_ui()
        self.apply_styles()
        self.show_welcome()

    def init_ui(self):
        role_display = {"student":"Студент","admin":"Администратор"}.get(self.user_role, self.user_role.capitalize())
        self.setWindowTitle(f"🏛️ МУИВ - {role_display}")
        self.setGeometry(100,100,1200,600)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Левая панель
        left_panel = QFrame()
        left_panel.setFixedWidth(300)
        left_layout = QVBoxLayout(left_panel)
        logo = QLabel("🏛️ МУИВ")
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet("font-size:42px; font-weight:bold; color:#8B0000; padding:10px;")
        left_layout.addWidget(logo)
        user_info = QLabel(f"👤 {role_display}")
        user_info.setAlignment(Qt.AlignCenter)
        user_info.setStyleSheet("font-size:14px; color:#555; margin-bottom:20px;")
        left_layout.addWidget(user_info)
        logout_btn = QPushButton("🚪 Выйти")
        logout_btn.clicked.connect(self.logout)
        left_layout.addWidget(logout_btn)
        left_layout.addSpacing(20)

        # Быстрая справка
        quick_group = QGroupBox("📌 Быстрая справка")
        quick_group.setStyleSheet("QGroupBox { font-weight:bold; border:1px solid #8B0000; border-radius:8px; margin-top:10px; }")
        quick_layout = QVBoxLayout()
        for text, kw in [("🎓 СПО","спо"), ("📖 Бакалавриат","бакалавриат"), ("💰 Стоимость","стоимость"),
                         ("⏰ Сроки","сроки"), ("📄 Поступление","документы"), ("📊 Проходные баллы","проходной балл")]:
            btn = QPushButton(text)
            btn.clicked.connect(lambda ch, q=kw: self.quick_question(q))
            btn.setStyleSheet("background:#8B0000; color:white; padding:6px; border-radius:6px; text-align:left;")
            quick_layout.addWidget(btn)
        if self.user_role == "student":
            for text, q in [("📅 Расписание","где найти расписание?"), ("📚 Электронная библиотека","ссылка на библиотеку")]:
                btn = QPushButton(text)
                btn.clicked.connect(lambda ch, qq=q: self.quick_question(qq))
                btn.setStyleSheet("background:#2c5e66; color:white; padding:6px; border-radius:6px;")
                quick_layout.addWidget(btn)
        quick_group.setLayout(quick_layout)
        left_layout.addWidget(quick_group)

        if self.user_role == "admin":
            admin_btn = QPushButton("⚙️ Панель администратора")
            admin_btn.setStyleSheet("background:#2c3e66; color:white; padding:8px; border-radius:8px;")
            admin_btn.clicked.connect(self.open_admin_panel)
            left_layout.addWidget(admin_btn)

        left_layout.addStretch()
        splitter.addWidget(left_panel)

        # Правая панель (чат)
        right_panel = QFrame()
        right_panel.setStyleSheet("background:rgba(255,255,240,0.9); border-radius:10px;")
        right_layout = QVBoxLayout(right_panel)
        chat_label = QLabel("💬 Чат с помощником")
        chat_label.setStyleSheet("font-size:18px; font-weight:bold; color:#8B0000;")
        right_layout.addWidget(chat_label)
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        bg_path = "fon.png"
        if os.path.exists(bg_path):
            self.chat_display.setStyleSheet(f"""
                QTextEdit {{
                    background: url({bg_path.replace('\\','/')}) no-repeat center center;
                    background-size: cover;
                    border: 2px solid #8B0000;
                    border-radius: 15px;
                    padding: 10px;
                    font-size: 14px;
                }}
            """)
        else:
            self.chat_display.setStyleSheet("background: rgba(255,255,255,0.9); border:2px solid #8B0000; border-radius:15px; padding:10px;")
        right_layout.addWidget(self.chat_display)
        input_layout = QHBoxLayout()
        self.question_input = QLineEdit()
        self.question_input.setPlaceholderText("Введите вопрос...")
        self.question_input.setStyleSheet("padding:8px; border-radius:10px; border:1px solid #8B0000;")
        self.question_input.returnPressed.connect(self.send_question)
        send_btn = QPushButton("🚀 Отправить")
        send_btn.setStyleSheet("background:#8B0000; color:white; padding:8px 15px; border-radius:10px;")
        send_btn.clicked.connect(self.send_question)
        clear_btn = QPushButton("🗑️ Очистить")
        clear_btn.setStyleSheet("background:#555; color:white; padding:8px 15px; border-radius:10px;")
        clear_btn.clicked.connect(self.clear_chat)
        input_layout.addWidget(self.question_input)
        input_layout.addWidget(send_btn)
        input_layout.addWidget(clear_btn)
        right_layout.addLayout(input_layout)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(1,2)

        if os.path.exists("fon.png"):
            self.setStyleSheet(f"QMainWindow {{ background-image: url(fon.png); background-repeat: no-repeat; background-position: center; background-attachment: fixed; }}")

    def apply_styles(self):
        self.setStyleSheet("QPushButton:hover { background: #A52A2A; } QLineEdit { background: white; } QGroupBox { font-size:13px; }")

    def show_welcome(self):
        role_display = {"student":"Студент","admin":"Администратор"}.get(self.user_role)
        welcome = f"""**🤖 Добро пожаловать, {role_display}!**

Я информационный помощник МУИВ. Задайте любой вопрос об университете.

Например:
• Какие есть специальности в колледже?
• Сколько стоит обучение?
• Расскажи о бакалавриате
• Какие проходные баллы?
• Что нужно сдавать на вступительных?

В левой панели вы найдёте быстрые ссылки на главные темы."""
        self.chat_display.append(welcome)
        self.chat_display.append("-" * 80)

    def quick_question(self, q):
        self.question_input.setText(q)
        self.send_question()

    def send_question(self):
        question = self.question_input.text().strip()
        if not question:
            return
        self.chat_display.append(f"👤 **Вы:** {question}")
        self.question_input.clear()
        student_id = None
        if self.user_role == "student":
            # В реальном приложении нужно передавать username, но для простоты оставим None
            # Чтобы тикеты работали, можно сохранить текущего пользователя. Для краткости – не реализовано.
            pass
        answer = self.chatbot.answer_question(question, student_id)
        self.chat_display.append(f"🤖 **Помощник:** {answer}")
        self.chat_display.append("-" * 80)
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())

    def clear_chat(self):
        self.chat_display.clear()
        self.chat_display.append("💬 Чат очищен")
        self.chat_display.append("-" * 80)

    def open_admin_panel(self):
        if self.user_role != "admin":
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Администрирование")
        dialog.resize(1000, 700)
        tabs = QTabWidget()
        tabs.addTab(AdminSpecialtiesTable(self.json_db, "spo"), "СПО")
        tabs.addTab(AdminSpecialtiesTable(self.json_db, "bachelor"), "Бакалавриат")
        tabs.addTab(AdminSpecialtiesTable(self.json_db, "specialist"), "Специалитет")
        tabs.addTab(AdminQATable(self.json_db), "Вопросы-ответы (JSON)")
        tabs.addTab(AdminUsersTable(self.user_manager), "Пользователи")
        tabs.addTab(AdminDataSourcesWidget(self.admin_db), "Источники данных")
        tabs.addTab(AdminAcademicFilesWidget(self.admin_db, self), "Академические файлы")
        tabs.addTab(AdminBotSettingsWidget(self.admin_db), "Настройки бота")
        tabs.addTab(AdminStatsWidget(self.admin_db, self.user_manager), "Статистика")
        layout = QVBoxLayout(dialog)
        layout.addWidget(tabs)
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        dialog.exec_()

    def logout(self):
        self.close()
        login = LoginWindow(self.user_manager)
        if login.exec_() == QDialog.Accepted:
            self.new_win = MUIvApp(login.user_role, self.user_manager, self.json_db, self.admin_db)
            self.new_win.show()
        else:
            QApplication.quit()


# ======================== ЗАПУСК ========================
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    user_manager = UserManager()
    admin_db = AdminDatabase()
    json_db = UniversityDatabase()
    login = LoginWindow(user_manager)
    if login.exec_() == QDialog.Accepted:
        main_win = MUIvApp(login.user_role, user_manager, json_db, admin_db)
        main_win.show()
        sys.exit(app.exec_())
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()