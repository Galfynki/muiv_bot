import sys
import json
import os
from pathlib import Path
import re
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QWidget, QPushButton, QTextEdit, QLabel, QProgressBar,
                             QLineEdit, QMessageBox, QSplitter, QFrame, QComboBox,
                             QGroupBox, QRadioButton, QButtonGroup)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPalette, QColor, QPixmap


class UniversityDatabase:
    """Класс для хранения и поиска информации о МУИВ"""

    def __init__(self):
        self.data = {
            "spo": {
                "title": "Среднее профессиональное образование (колледж)",
                "specialties": [],
                "costs": {}
            },
            "bachelor": {
                "title": "Бакалавриат",
                "specialties": [],
                "costs": {}
            },
            "specialist": {
                "title": "Специалитет",
                "specialties": [],
                "costs": {}
            }
        }
        self._load_data()

    def _load_data(self):
        """Загрузка данных из встроенных таблиц"""

        # ============ СПО (колледж) ============
        spo_specialties = [
            {"code": "38.02.01", "name": "Экономика и бухгалтерский учет", "qualification": "Бухгалтер",
             "duration_full_9": "2г 10м", "duration_full_11": "1г 10м", "form": "очная"},
            {"code": "38.02.03", "name": "Операционная деятельность в логистике",
             "qualification": "Операционный логист",
             "duration_full_9": "2г 10м", "duration_full_11": "1г 10м", "form": "очная"},
            {"code": "38.02.08", "name": "Торговое дело", "qualification": "Специалист торгового дела",
             "duration_full_9": "2г 10м", "duration_full_11": "1г 10м", "form": "очная"},
            {"code": "38.02.06", "name": "Финансы", "qualification": "Финансист",
             "duration_full_9": "2г 10м", "duration_full_11": "1г 10м", "form": "очная"},
            {"code": "38.02.07", "name": "Банковское дело", "qualification": "Специалист банковского дела",
             "duration_full_9": "2г 10м", "duration_full_11": "1г 10м", "form": "очная"},
            {"code": "40.02.04", "name": "Юриспруденция (социальное обеспечение)",
             "qualification": "Юрист в сфере социального обеспечения",
             "duration_full_9": "2г 10м", "duration_full_11": "1г 10м", "form": "очная"},
            {"code": "40.02.04", "name": "Юриспруденция (судебное администрирование)",
             "qualification": "Юрист в сфере судебного администрирования",
             "duration_full_9": "2г 10м", "duration_full_11": "1г 10м", "form": "очная"},
            {"code": "42.02.01", "name": "Реклама", "qualification": "Специалист по рекламе",
             "duration_full_9": "2г 10м", "duration_full_11": "1г 10м", "form": "очная"},
            {"code": "09.02.01", "name": "Компьютерные системы и комплексы",
             "qualification": "Специалист по компьютерным системам",
             "duration_full_9": "3г 10м", "duration_full_11": "2г 10м", "form": "очная"},
            {"code": "09.02.11", "name": "Разработка и управление программным обеспечением",
             "qualification": "Программист",
             "duration_full_9": "3г 10м", "duration_full_11": "2г 10м", "form": "очная"},
            {"code": "09.02.12", "name": "Техническая эксплуатация и сопровождение ИС",
             "qualification": "Специалист по технической эксплуатации",
             "duration_full_9": "2г 10м", "duration_full_11": "1г 10м", "form": "очная"},
            {"code": "44.02.01", "name": "Дошкольное образование",
             "qualification": "Воспитатель детей дошкольного возраста",
             "duration_full_9": "3г 10м", "duration_full_11": "2г 10м", "form": "очная"},
            {"code": "44.02.02", "name": "Преподавание в начальных классах",
             "qualification": "Учитель начальных классов",
             "duration_full_9": None, "duration_full_11": "2г 10м", "form": "очная"},
            {"code": "10.02.05", "name": "Обеспечение информационной безопасности",
             "qualification": "Техник по защите информации",
             "duration_full_9": None, "duration_full_11": "2г 10м", "form": "очная"},
            {"code": "49.02.01", "name": "Физическая культура", "qualification": "Педагог по физической культуре",
             "duration_full_9": "3г 10м", "duration_full_11": "2г 10м", "form": "очная"},
            {"code": "54.02.01", "name": "Дизайн (по отраслям)", "qualification": "Дизайнер",
             "duration_full_9": "3г 10м", "duration_full_11": "2г 10м", "form": "очная"},
            {"code": "43.02.17", "name": "Технологии индустрии красоты",
             "qualification": "Специалист индустрии красоты",
             "duration_full_9": None, "duration_full_11": "1г 10м", "form": "очная"},
            {"code": "09.02.13", "name": "Интеграция с технологиями ИИ", "qualification": "Специалист по работе с ИИ",
             "duration_full_9": "3г 10м", "duration_full_11": "2г 10м", "form": "очная"},
            {"code": "38.02.09", "name": "Конгрессно-выставочная деятельность",
             "qualification": "Специалист конгрессно-выставочной деятельности",
             "duration_full_9": "2г 10м", "duration_full_11": "1г 10м", "form": "очная"},
            {"code": "09.02.09", "name": "Веб-разработка", "qualification": "Разработчик веб-приложений",
             "duration_full_9": "2г 10м", "duration_full_11": "1г 10м", "form": "очная"},
            {"code": "23.02.07", "name": "Техническое обслуживание автотранспорта",
             "qualification": "Специалист по ТО автотранспорта",
             "duration_full_9": None, "duration_full_11": "2г 10м", "form": "очная"},
            # Заочная форма СПО
            {"code": "38.02.03", "name": "Операционная деятельность в логистике (заочная)",
             "qualification": "Операционный логист",
             "duration_full_9": "3г 4м", "duration_full_11": "2г 4м", "form": "заочная"},
            {"code": "38.02.08", "name": "Торговое дело (заочная)", "qualification": "Специалист торгового дела",
             "duration_full_9": "3г 4м", "duration_full_11": "2г 4м", "form": "заочная"},
            {"code": "38.02.07", "name": "Банковское дело (заочная)", "qualification": "Специалист банковского дела",
             "duration_full_9": "3г 4м", "duration_full_11": "2г 4м", "form": "заочная"},
            {"code": "44.02.01", "name": "Дошкольное образование (заочная)", "qualification": "Воспитатель",
             "duration_full_9": "4г 4м", "duration_full_11": "3г 4м", "form": "заочная"},
            {"code": "42.02.01", "name": "Реклама (заочная)", "qualification": "Специалист по рекламе",
             "duration_full_9": "3г 4м", "duration_full_11": "2г 4м", "form": "заочная"},
            {"code": "38.02.06", "name": "Финансы (заочная)", "qualification": "Финансист",
             "duration_full_9": "3г 4м", "duration_full_11": "2г 4м", "form": "заочная"},
            {"code": "09.02.11", "name": "Разработка ПО (заочная)", "qualification": "Программист",
             "duration_full_9": "4г 4м", "duration_full_11": "3г 4м", "form": "заочная"},
        ]

        # Стоимость СПО
        spo_costs = {
            "38.02.07": {"full_9": 100000, "full_11": 110000, "distance": 50000},
            "09.02.09": {"full_9": 110000, "full_11": 120000},
            "54.02.01": {"full_9": 100000, "full_11": 110000},
            "44.02.01": {"full_9": 90000, "full_11": 100000, "distance": 50000},
            "09.02.10": {"full_9": 110000, "full_11": 120000},
            "09.02.01": {"full_9": 110000, "full_11": 120000},
            "43.02.16": {"full_9": 80000, "full_11": 90000},
            "10.02.05": {"full_11": 80000},
            "38.02.03": {"full_9": 100000, "full_11": 110000, "distance": 50000},
            "44.02.02": {"full_11": 80000},
            "09.02.11": {"full_9": 110000, "full_11": 120000, "distance": 50000},
            "42.02.01": {"full_9": 100000, "full_11": 110000, "distance": 50000},
            "09.02.06": {"full_9": 80000, "full_11": 120000, "distance": 50000},
            "23.02.07": {"full_11": 80000},
            "43.02.17": {"full_11": 80000},
            "38.02.08": {"full_9": 100000, "full_11": 110000, "distance": 50000},
            "49.02.01": {"full_9": 90000, "full_11": 100000},
            "38.02.06": {"full_9": 90000, "full_11": 100000, "distance": 50000},
            "38.02.01": {"full_9": 100000, "full_11": 110000},
            "40.02.04": {"full_9": 100000, "full_11": 110000},
        }

        for spec in spo_specialties:
            code_base = spec["code"].split()[0]
            cost_info = spo_costs.get(code_base, {})
            spec["costs"] = cost_info
            self.data["spo"]["specialties"].append(spec)

        # ============ Бакалавриат ============
        bachelor_specialties = [
            {"code": "38.03.05", "name": "Бизнес-информатика",
             "profiles": ["Игровая компьютерная индустрия", "Цифровой дизайн и веб-разработка", "Бизнес-аналитик 1С"],
             "duration": "4 года", "form": "очная"},
            {"code": "38.03.04", "name": "Государственное и муниципальное управление",
             "profiles": ["Государственное и муниципальное управление", "Цифровое государство"],
             "duration": "4 года", "form": "очная"},
            {"code": "38.03.02", "name": "Менеджмент",
             "profiles": ["Логистика", "Маркетинг", "Управление проектами", "Цифровой менеджмент"],
             "duration": "4 года", "form": "очная"},
            {"code": "09.03.03", "name": "Прикладная информатика",
             "profiles": ["Искусственный интеллект", "Корпоративные ИС", "Кибербезопасность"],
             "duration": "4 года", "form": "очная"},
            {"code": "44.03.02", "name": "Психолого-педагогическое образование",
             "profiles": ["Психология и социальная педагогика"],
             "duration": "4 года", "form": "очная"},
            {"code": "44.03.05", "name": "Педагогическое образование",
             "profiles": ["Русский язык, Английский язык/Математика"],
             "duration": "5 лет", "form": "очная"},
            {"code": "44.03.03", "name": "Специальное (дефектологическое) образование",
             "profiles": ["Специальная психология"],
             "duration": "4 года", "form": "очная"},
            {"code": "42.03.01", "name": "Реклама и связи с общественностью", "profiles": ["Реклама в комм. сфере"],
             "duration": "4 года", "form": "очная"},
            {"code": "43.03.02", "name": "Туризм", "profiles": ["Технология туристских услуг"],
             "duration": "4 года", "form": "очная"},
            {"code": "38.03.03", "name": "Управление персоналом", "profiles": ["Кадровый консалтинг"],
             "duration": "4 года", "form": "очная"},
            {"code": "38.03.01", "name": "Экономика",
             "profiles": ["Бизнес-аналитика", "Бухгалтерский учет", "Финансовая аналитика"],
             "duration": "4 года", "form": "очная"},
            {"code": "40.03.01", "name": "Юриспруденция", "profiles": ["Гражданско-правовой", "Уголовно-правовой"],
             "duration": "4 года", "form": "очная"},
        ]

        # Стоимость бакалавриата
        bachelor_costs = {
            "38.03.05": {"full": 166000, "part_time": 100000, "distance": 50000},
            "38.03.04": {"full": 166000, "part_time": 100000, "distance": 50000},
            "38.03.02": {"full": 166000, "part_time": 100000, "distance": 50000},
            "09.03.03": {"full": 150000, "distance": 95000},
            "44.03.02": {"full": 130000, "distance": 90000},
            "44.03.05": {"full": 130000, "distance": 45000},
            "44.03.03": {"full": 110000, "part_time": 75000, "distance": 43000},
            "42.03.01": {"full": 166000, "distance": 50000},
            "43.03.02": {"full": 130000, "part_time": 90000, "distance": 45000},
            "38.03.03": {"part_time": 100000, "distance": 50000},
            "38.03.01": {"full": 166000, "part_time": 100000, "distance": 50000},
            "40.03.01": {"full": 166000, "part_time": 100000, "distance": 50000},
        }

        for spec in bachelor_specialties:
            cost_info = bachelor_costs.get(spec["code"], {})
            spec["costs"] = cost_info
            self.data["bachelor"]["specialties"].append(spec)

        # ============ Специалитет ============
        specialist_specialties = [
            {"code": "38.05.02", "name": "Таможенное дело", "profiles": ["Таможенные платежи"],
             "duration": "5 лет", "form": "очная"},
            {"code": "38.03.05", "name": "Бизнес-информатика (специалитет)", "profiles": ["Различные профили"],
             "duration": "5 лет", "form": "очная"},
        ]

        for spec in specialist_specialties:
            self.data["specialist"]["specialties"].append(spec)

    def search(self, query):
        """Поиск информации по запросу"""
        query_lower = query.lower()
        results = []

        # Поиск по СПО
        for spec in self.data["spo"]["specialties"]:
            if (query_lower in spec["name"].lower() or
                    query_lower in spec["code"].lower() or
                    query_lower in spec["qualification"].lower()):
                results.append(("СПО (колледж)", spec))

        # Поиск по бакалавриату
        for spec in self.data["bachelor"]["specialties"]:
            if (query_lower in spec["name"].lower() or
                    query_lower in spec["code"].lower()):
                results.append(("Бакалавриат", spec))

        return results

    def get_all_info(self):
        """Получить всю информацию для отображения"""
        return self.data


class MUIvChatBot:
    """Чат-бот на основе базы данных МУИВ"""

    def __init__(self):
        self.db = UniversityDatabase()
        self.qa_pairs = self._build_qa_pairs()

    def _build_qa_pairs(self):
        """Построение пар вопрос-ответ из базы данных"""
        qa_pairs = []

        # Общая информация
        qa_pairs.append({
            "keywords": ["привет", "здравствуй", "добрый день", "добрый вечер", "доброе утро"],
            "answer": "Здравствуйте! Я - информационный помощник МУИВ. Я могу рассказать вам о специальностях, сроках обучения, стоимости и условиях поступления. Чем могу помочь?"
        })

        qa_pairs.append({
            "keywords": ["кто ты", "ты кто", "что ты умеешь", "помощник"],
            "answer": "Я - виртуальный помощник Московского университета имени С.Ю. Витте (МУИВ). Я знаю информацию о специальностях, формах обучения, сроках и стоимости образования. Задавайте вопросы!"
        })

        # СПО информация
        qa_pairs.append({
            "keywords": ["спо", "колледж", "среднее профессиональное", "после 9", "после 11"],
            "answer": self._get_spo_overview()
        })

        qa_pairs.append({
            "keywords": ["бакалавриат", "высшее", "4 года", "бакалавр"],
            "answer": self._get_bachelor_overview()
        })

        qa_pairs.append({
            "keywords": ["специалитет", "специалист", "5 лет", "6 лет"],
            "answer": self._get_specialist_overview()
        })

        # Стоимость
        qa_pairs.append({
            "keywords": ["стоимость", "цена", "сколько стоит", "оплата", "рублей", "семестр"],
            "answer": self._get_cost_info
        })

        # Сроки обучения
        qa_pairs.append({
            "keywords": ["срок", "длится", "сколько лет", "сколько учиться", "продолжительность"],
            "answer": self._get_duration_info
        })

        # Поступление
        qa_pairs.append({
            "keywords": ["поступление", "документы", "поступить", "экзамены", "егэ", "оги", "прием"],
            "answer": "📄 **Поступление в МУИВ**\n\nДля поступления в МУИВ вам потребуются:\n• Аттестат об образовании (9 или 11 классов)\n• Паспорт\n• Фотографии 3x4\n• Заявление о приеме\n• Документы, подтверждающие льготы (при наличии)\n\nПриемная комиссия работает с июня по август. Более подробную информацию можно получить по телефону или на сайте."
        })

        return qa_pairs

    def _get_spo_overview(self):
        """Обзор СПО"""
        spo = self.db.data["spo"]
        specialties = spo["specialties"][:10]
        spec_list = "\n".join([f"• {s['code']} - {s['name']} ({s['qualification']})" for s in specialties])
        return f"""**🎓 {spo['title']}**

Основные специальности:
{spec_list}

...и еще {len(spo['specialties']) - 10} специальностей.

**Формы обучения:** Очная, заочная (с применением ДОТ)
**Сроки:** от 1г 10м до 4г 4м в зависимости от формы и базы образования
**Стоимость:** от 50 000 до 120 000 рублей за семестр

Для уточнения информации по конкретной специальности, напишите её название или код."""

    def _get_bachelor_overview(self):
        """Обзор бакалавриата"""
        bachelor = self.db.data["bachelor"]
        specialties = bachelor["specialties"][:8]
        spec_list = "\n".join([f"• {s['code']} - {s['name']}" for s in specialties])
        return f"""**🎓 {bachelor['title']}**

Бакалавриат - первая ступень высшего образования. Продолжительность: 4-5 лет.

Основные направления:
{spec_list}

...и еще {len(bachelor['specialties']) - 8} направлений.

**Формы обучения:** Очная, очно-заочная, заочная (с ДОТ)
**Стоимость:** от 43 000 до 166 000 рублей за семестр

По окончании выдается диплом государственного образца."""

    def _get_specialist_overview(self):
        """Обзор специалитета"""
        return """**🎓 Специалитет**

Специалитет - традиционная форма высшего образования в России.

• Срок обучения: 5-6 лет
• Квалификация: "специалист" с указанием специализации
• Диплом государственного образца

**Основные направления:**
• 38.05.02 - Таможенное дело
• 38.03.05 - Бизнес-информатика

После окончания специалитета можно продолжить обучение в магистратуре или аспирантуре."""

    def _get_cost_info(self, query=""):
        """Получение информации о стоимости"""
        lines = ["💰 **Стоимость обучения в МУИВ**\n"]

        lines.append("**СПО (колледж) - очная форма:**")
        lines.append("• 38.02.07 Банковское дело: 100 000 - 110 000 руб/семестр")
        lines.append("• 09.02.01 Компьютерные системы: 110 000 руб/семестр")
        lines.append("• 38.02.03 Логистика: 100 000 - 110 000 руб/семестр")
        lines.append("• 44.02.01 Дошкольное образование: 90 000 - 100 000 руб/семестр\n")

        lines.append("**Бакалавриат - очная форма:**")
        lines.append("• Экономика, Менеджмент, Юриспруденция: 166 000 руб/семестр")
        lines.append("• Прикладная информатика: 150 000 руб/семестр")
        lines.append("• Психология: 130 000 руб/семестр\n")

        lines.append("**Заочная/дистанционная форма:**")
        lines.append("• От 43 000 до 95 000 рублей за семестр")
        lines.append("\n*Точная стоимость зависит от специальности и формы обучения.")

        return "\n".join(lines)

    def _get_duration_info(self, query=""):
        """Получение информации о сроках обучения"""
        lines = ["⏰ **Сроки обучения в МУИВ**\n"]

        lines.append("**СПО (колледж):**")
        lines.append("• На базе 9 классов: 2 года 10 месяцев - 3 года 10 месяцев")
        lines.append("• На базе 11 классов: 1 год 10 месяцев - 2 года 10 месяцев")
        lines.append("• Заочная форма: +1 год к очной форме\n")

        lines.append("**Бакалавриат:**")
        lines.append("• Очная форма: 4 года (5 лет для педагогического образования)")
        lines.append("• Очно-заочная: 4 года 6 месяцев")
        lines.append("• Заочная: 4 года 6 месяцев - 6 лет\n")

        lines.append("**Специалитет:**")
        lines.append("• Очная форма: 5 лет")
        lines.append("• Заочная форма: 6 лет\n")

        lines.append("*Возможно ускоренное обучение по индивидуальному плану.*")

        return "\n".join(lines)

    def answer_question(self, question):
        """Ответ на вопрос"""
        question_lower = question.lower()

        # Поиск по ключевым словам
        for qa in self.qa_pairs:
            for keyword in qa["keywords"]:
                if keyword in question_lower:
                    if callable(qa["answer"]):
                        return qa["answer"](question)
                    return qa["answer"]

        # Поиск по специальностям
        search_results = self.db.search(question_lower)
        if search_results:
            response = "🔍 **Найдено по вашему запросу:**\n\n"
            for level, spec in search_results[:5]:
                response += f"**{level}**\n"
                response += f"📌 {spec['code']} - {spec['name']}\n"
                if 'qualification' in spec:
                    response += f"👨‍🎓 Квалификация: {spec['qualification']}\n"
                if 'duration_full_9' in spec and spec['duration_full_9']:
                    response += f"📅 Срок (9 кл.): {spec['duration_full_9']}\n"
                if 'duration_full_11' in spec and spec['duration_full_11']:
                    response += f"📅 Срок (11 кл.): {spec['duration_full_11']}\n"
                if 'costs' in spec and spec['costs']:
                    response += f"💰 Стоимость: от {min(spec['costs'].values()) if spec['costs'] else 'уточняйте'} руб/семестр\n"
                response += "\n"
            return response

        # Ответ по умолчанию
        return """❓ **Не нашел точного ответа на ваш вопрос.**

Я могу помочь с информацией о:
• Специальностях СПО (колледж)
• Направлениях бакалавриата и специалитета
• Стоимости обучения
• Сроках обучения
• Поступлении и документах

Попробуйте переформулировать вопрос или уточните:
- код специальности (например, "38.02.07")
- название направления
- или задайте вопрос о конкретном аспекте обучения"""


class ParserThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)
    log_message = pyqtSignal(str)

    def __init__(self):
        super().__init__()

    def run(self):
        self.log_message.emit("📚 Загрузка базы данных специальностей МУИВ...")
        self.progress.emit(50)

        # Создаем базу данных
        db = UniversityDatabase()
        data = db.get_all_info()

        self.progress.emit(100)
        self.log_message.emit("✅ База данных успешно загружена!")
        self.finished.emit(data)


class MUIvApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.parser_thread = None
        self.chatbot = None
        self.init_ui()
        self.apply_theme()
        self.init_chatbot()

    def init_chatbot(self):
        """Инициализация чат-бота"""
        self.chatbot = MUIvChatBot()
        self.status_label.setText("✅ Чат-бот готов к работе!")
        self.parse_btn.setText("📚 База данных загружена")
        self.parse_btn.setEnabled(False)

        # Приветственное сообщение
        welcome_msg = """**🤖 Добро пожаловать в чат-бота МУИВ!**

Я - информационный помощник Московского университета имени С.Ю. Витте.

**Что я могу:**
• Рассказать о специальностях СПО (колледж)
• Предоставить информацию о бакалавриате и специалитете
• Сообщить стоимость и сроки обучения
• Помочь с вопросами поступления

**Примеры вопросов:**
• Какие есть специальности в колледже?
• Сколько стоит обучение на юриспруденции?
• Как долго учиться после 9 класса?
• Что такое бакалавриат?
• Расскажи о специальности 38.02.07

Задайте свой вопрос!"""
        self.chat_display.append(welcome_msg)
        self.chat_display.append("-" * 80)

    def init_ui(self):
        self.setWindowTitle("🏛️ МУИВ Информационный помощник")
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

        # Логотип
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        logo_path = "logo.jpg"
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo_label.setPixmap(pixmap)
            else:
                logo_label.setText("🏛️")
                logo_label.setStyleSheet("font-size: 48px;")
        else:
            logo_label.setText("🏛️ МУИВ")
            logo_label.setStyleSheet("font-size: 36px; font-weight: bold;")
        left_layout.addWidget(logo_label)
        left_layout.addSpacing(10)

        # Заголовок
        title = QLabel("🏛️ МУИВ")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        left_layout.addWidget(title)

        subtitle = QLabel("Информационный помощник")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-size: 14px; color: #666;")
        left_layout.addWidget(subtitle)

        left_layout.addSpacing(20)

        # Кнопка информации
        self.parse_btn = QPushButton("📚 База данных")
        self.parse_btn.setEnabled(False)
        left_layout.addWidget(self.parse_btn)

        left_layout.addSpacing(10)

        # Группа быстрых ссылок
        quick_group = QGroupBox("📌 Быстрая информация")
        quick_layout = QVBoxLayout()

        spo_btn = QPushButton("🎓 СПО (колледж)")
        spo_btn.clicked.connect(lambda: self.quick_question("расскажи о спо"))
        quick_layout.addWidget(spo_btn)

        bachelor_btn = QPushButton("📖 Бакалавриат")
        bachelor_btn.clicked.connect(lambda: self.quick_question("расскажи о бакалавриате"))
        quick_layout.addWidget(bachelor_btn)

        cost_btn = QPushButton("💰 Стоимость обучения")
        cost_btn.clicked.connect(lambda: self.quick_question("сколько стоит обучение"))
        quick_layout.addWidget(cost_btn)

        duration_btn = QPushButton("⏰ Сроки обучения")
        duration_btn.clicked.connect(lambda: self.quick_question("сроки обучения"))
        quick_layout.addWidget(duration_btn)

        admission_btn = QPushButton("📄 Поступление")
        admission_btn.clicked.connect(lambda: self.quick_question("документы для поступления"))
        quick_layout.addWidget(admission_btn)

        quick_group.setLayout(quick_layout)
        left_layout.addWidget(quick_group)

        # Прогресс бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        left_layout.addWidget(self.progress_bar)

        # Статус
        self.status_label = QLabel("🔄 Загрузка базы данных...")
        left_layout.addWidget(self.status_label)

        left_layout.addStretch()

        # Правая панель - чат
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        splitter.addWidget(right_panel)

        # Чат область
        chat_label = QLabel("💬 Задайте вопрос о МУИВ")
        right_layout.addWidget(chat_label)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)

        # Добавляем фоновое изображение
        background_image_path = "fon.png"
        if os.path.exists(background_image_path):
            # Экранируем слеши для CSS и создаем путь
            bg_path = background_image_path.replace('\\', '/')
            self.chat_display.setStyleSheet(f"""
                QTextEdit {{
                    background: url({bg_path}) no-repeat center center;
                    background-size: cover;
                    border: 2px solid #8B0000;
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
                    background: #FFFFFF;
                    border: 2px solid #8B0000;
                    border-radius: 10px;
                    padding: 15px;
                    font-size: 14px;
                }
            """)
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
        send_btn.setStyleSheet("""
            QPushButton {
                background: #8B0000;
                padding: 12px 20px;
                min-width: 100px;
            }
        """)
        input_layout.addWidget(send_btn)

        clear_btn = QPushButton("🗑️ Очистить")
        clear_btn.clicked.connect(self.clear_chat)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: #555;
                padding: 12px 15px;
                min-width: 80px;
            }
            QPushButton:hover {
                background: #777;
            }
        """)
        input_layout.addWidget(clear_btn)

        right_layout.addLayout(input_layout)

        # Растягиваем правую панель
        splitter.setStretchFactor(1, 2)

    def quick_question(self, question):
        """Быстрый вопрос"""
        self.question_input.setText(question)
        self.send_question()

    def set_example_question(self, question):
        self.question_input.setText(question)
        self.send_question()

    def clear_chat(self):
        """Очистка чата"""
        self.chat_display.clear()
        self.chat_display.append("💬 **Чат очищен**")
        self.chat_display.append("-" * 80)

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

        self.setStyleSheet("""
            QMainWindow {
                background-color: #FFFFFF;
            }
            QPushButton {
                background: #8B0000;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #A52A2A;
            }
            QPushButton:pressed {
                background: #6B0000;
            }
            QLineEdit {
                padding: 10px;
                border: 2px solid #ddd;
                border-radius: 8px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #8B0000;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #8B0000;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #8B0000;
            }
            QLabel {
                color: #333;
            }
        """)

    def send_question(self):
        question = self.question_input.text().strip()
        if not question:
            return

        self.chat_display.append(f"👤 **Вы:** {question}")
        self.question_input.clear()

        self.chat_display.append("🤖 **МУИВ-бот:** Думаю над ответом...")
        QApplication.processEvents()

        if not self.chatbot:
            self.chat_display.append("❌ Чат-бот не загружен. Перезапустите приложение.")
            return

        answer = self.chatbot.answer_question(question)

        # Заменяем последнее сообщение
        cursor = self.chat_display.textCursor()
        cursor.movePosition(cursor.End)
        cursor.movePosition(cursor.StartOfLine, cursor.KeepAnchor)
        cursor.removeSelectedText()
        cursor.deletePreviousChar()

        self.chat_display.append(answer)
        self.chat_display.append("-" * 80)
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )


def main():
    app = QApplication(sys.argv)
    window = MUIvApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()