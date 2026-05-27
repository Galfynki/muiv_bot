import subprocess
import sys

# Автоматическая установка недостающих библиотек
try:
    import accelerate
    import transformers
    import torch
except ImportError:
    print("Устанавливаем accelerate, transformers, torch...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "accelerate>=1.1.0", "transformers", "torch", "--quiet"])

import os
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict, Counter
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import torch
from torch.utils.data import Dataset
from transformers import (
    AutoTokenizer, AutoModelForSequenceClassification,
    TrainingArguments, Trainer, EarlyStoppingCallback
)


# ------------------------------------------------------------
# 1. ЗАГРУЗКА ВОПРОСОВ И ОТВЕТОВ ИЗ CSV
# ------------------------------------------------------------
def load_csv_qa(csv_path="university.csv"):
    """
    Загружает вопросы и ответы из CSV.
    Возвращает: список вопросов (для обучения) и словарь вопрос->ответ (для построения intent_mapping).
    """
    questions = []
    qa_dict = {}
    if not os.path.exists(csv_path):
        print("⚠️ Файл university.csv не найден, пропускаем.")
        return questions, qa_dict
    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
        if 'question' in df.columns and 'answer' in df.columns:
            # Убираем дубликаты вопросов, оставляем первый ответ
            df_unique = df.drop_duplicates(subset='question')
            for _, row in df_unique.iterrows():
                q = row['question'].strip()
                a = row['answer'].strip()
                if q and a:
                    questions.append(q)
                    qa_dict[q] = a
            print(f"📌 Из CSV загружено {len(questions)} уникальных вопросов с ответами.")
        else:
            print("⚠️ В CSV нет столбцов 'question' и/или 'answer'")
    except Exception as e:
        print(f"Ошибка чтения CSV: {e}")
    return questions, qa_dict


# ------------------------------------------------------------
# 2. ФИКСИРУЕМ ВОПРОСЫ ИЗ ПРИЛОЖЕНИЯ (PyQt5 код)
# ------------------------------------------------------------
def get_questions_from_app():
    questions = []
    quick_buttons = [
        ("спо", 2), ("бакалавриат", 3), ("стоимость", 5), ("сроки", 6),
        ("документы", 7), ("проходной балл", 10), ("вступительные испытания", 11)
    ]
    for q, intent in quick_buttons:
        questions.append((q, intent))
        questions.append((f"расскажи про {q}", intent))
        questions.append((f"что такое {q}", intent))
        questions.append((f"{q} в муив", intent))

    student_buttons = [("где найти расписание занятий?", 8), ("ссылка на электронную библиотеку", 9)]
    for q, intent in student_buttons:
        questions.append((q, intent))
        questions.append((q.lower(), intent))

    keywords_for_qa = {
        "привет": 0, "здравствуй": 0, "добрый день": 0, "добрый вечер": 0, "доброе утро": 0,
        "кто ты": 1, "ты кто": 1, "что ты умеешь": 1, "помощник": 1,
        "спо": 2, "колледж": 2, "среднее профессиональное": 2, "после 9": 2, "после 11": 2,
        "бакалавриат": 3, "высшее": 3, "4 года": 3, "бакалавр": 3,
        "специалитет": 4, "специалист": 4, "5 лет": 4, "6 лет": 4,
        "стоимость": 5, "цена": 5, "сколько стоит": 5, "оплата": 5, "рублей": 5, "семестр": 5,
        "срок": 6, "длится": 6, "сколько лет": 6, "сколько учиться": 6, "продолжительность": 6,
        "поступление": 7, "документы": 7, "поступить": 7, "экзамены": 7, "егэ": 7, "оги": 7, "прием": 7,
        "расписание": 8, "расписание занятий": 8, "пары": 8, "когда занятия": 8,
        "библиотека": 9, "электронная библиотека": 9, "книги": 9, "учебники": 9,
        "проходной балл": 10, "проходные баллы": 10, "баллы для поступления": 10, "минимальный балл": 10,
        "вступительные испытания": 11, "экзамены": 11, "вступительные": 11, "что сдавать": 11
    }
    for kw, intent in keywords_for_qa.items():
        if len(kw) > 3:
            questions.append((f"что такое {kw}", intent))
            questions.append((f"расскажи про {kw}", intent))
            questions.append((kw, intent))

    extra_phrases = [
        ("какие специальности есть в колледже", 2), ("сколько стоит обучение", 5),
        ("какие документы нужны для поступления", 7), ("как поступить в муив", 7),
        ("когда начинаются занятия", 8), ("есть ли электронная библиотека", 9),
        ("какой проходной балл на бюджет", 10), ("что нужно сдавать на юриста", 11),
    ]
    for q, intent in extra_phrases:
        questions.append((q, intent))

    unique_questions = list(set(questions))
    print(f"📌 Из приложения извлечено {len(unique_questions)} уникальных вопросов.")
    return unique_questions


# ------------------------------------------------------------
# 3. ОПРЕДЕЛЕНИЕ ИНТЕНТОВ ПО КЛЮЧЕВЫМ СЛОВАМ
# ------------------------------------------------------------
INTENTS = {
    0: {"name": "приветствие"},
    1: {"name": "общее_инфо"},
    2: {"name": "спо"},
    3: {"name": "бакалавриат"},
    4: {"name": "специалитет"},
    5: {"name": "стоимость"},
    6: {"name": "сроки"},
    7: {"name": "поступление"},
    8: {"name": "расписание"},
    9: {"name": "библиотека"},
    10: {"name": "проходной_балл"},
    11: {"name": "вступительные"},
}

KEYWORDS = {
    0: ["привет", "здравствуй", "добрый день", "доброе утро", "добрый вечер", "здрасьте", "приветствую"],
    1: ["кто ты", "ты кто", "что ты умеешь", "расскажи о себе", "твои возможности", "какой ты помощник"],
    2: ["спо", "колледж", "среднее профессиональное", "после 9 класса", "после 11 класса", "колледж при вузе",
        "специальности колледжа"],
    3: ["бакалавриат", "высшее образование", "бакалавр", "4 года обучения", "направления бакалавриата"],
    4: ["специалитет", "специалист", "5 лет", "специалитет муив"],
    5: ["стоимость", "цена", "сколько стоит", "оплата", "рублей", "семестр", "платное обучение", "ценник"],
    6: ["срок обучения", "сколько учиться", "длится обучение", "продолжительность", "лет учиться"],
    7: ["поступление", "документы", "поступить", "экзамены", "егэ", "оги", "прием", "приемная комиссия",
        "как поступить"],
    8: ["расписание", "расписание занятий", "пары", "когда занятия"],
    9: ["библиотека", "электронная библиотека", "книги", "учебники", "библиотека муив"],
    10: ["проходной балл", "проходные баллы", "баллы для поступления", "минимальный балл"],
    11: ["вступительные испытания", "что сдавать", "вступительные экзамены", "вступительные"],
}


def get_intent_by_keywords(text):
    text_lower = text.lower()
    scores = {}
    for intent_id, kw_list in KEYWORDS.items():
        score = sum(1 for kw in kw_list if kw in text_lower)
        if score > 0:
            scores[intent_id] = score
    if not scores:
        return -1
    return max(scores, key=scores.get)


# ------------------------------------------------------------
# 4. ГЕНЕРАЦИЯ ВСЕХ ПРИМЕРОВ (шаблоны + CSV + приложение)
# ------------------------------------------------------------
def generate_all_examples(csv_questions):
    examples = []
    # Шаблонные фразы
    templates = {
        0: ["привет", "здравствуй", "добрый день", "доброе утро", "добрый вечер", "здрасьте", "приветствую"],
        1: ["кто ты", "ты кто", "что ты умеешь", "расскажи о себе", "твои возможности", "какой ты помощник"],
        2: ["спо", "колледж", "среднее профессиональное", "после 9 класса", "после 11 класса", "колледж при вузе",
            "специальности колледжа"],
        3: ["бакалавриат", "высшее образование", "бакалавр", "4 года обучения", "направления бакалавриата"],
        4: ["специалитет", "специалист", "5 лет", "специалитет муив"],
        5: ["стоимость", "цена", "сколько стоит", "оплата", "рублей", "семестр", "платное обучение", "ценник"],
        6: ["срок обучения", "сколько учиться", "длится обучение", "продолжительность", "лет учиться"],
        7: ["поступление", "документы", "поступить", "экзамены", "егэ", "оги", "прием", "приемная комиссия",
            "как поступить"],
        8: ["расписание", "расписание занятий", "пары", "когда занятия"],
        9: ["библиотека", "электронная библиотека", "книги", "учебники", "библиотека муив"],
        10: ["проходной балл", "проходные баллы", "баллы для поступления", "минимальный балл"],
        11: ["вступительные испытания", "что сдавать", "вступительные экзамены", "вступительные"],
    }
    for intent_id, phrases in templates.items():
        for phrase in phrases:
            examples.append((phrase, intent_id))
            examples.append((f"расскажи про {phrase}", intent_id))
            examples.append((f"что такое {phrase}", intent_id))
            examples.append((f"уточните пожалуйста по {phrase}", intent_id))
            examples.append((f"информация о {phrase}", intent_id))

    # Вопросы из CSV (размечаем интенты)
    labeled_from_csv = 0
    for q in csv_questions:
        intent = get_intent_by_keywords(q)
        if intent != -1:
            examples.append((q, intent))
            labeled_from_csv += 1
            examples.append((q.lower(), intent))
            if not q.endswith('?'):
                examples.append((q + '?', intent))
    print(f"📌 Из CSV размечено {labeled_from_csv} уникальных вопросов.")

    # Вопросы из приложения (уже с интентами)
    app_qs = get_questions_from_app()
    examples.extend(app_qs)

    examples = list(set(examples))
    print(f"✅ Итого сгенерировано {len(examples)} уникальных примеров.")
    return examples


# ------------------------------------------------------------
# 5. ДАТАСЕТ PYTORCH
# ------------------------------------------------------------
class IntentDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_len=64):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = str(self.texts[idx])
        label = self.labels[idx]
        encoding = self.tokenizer(text, truncation=True, padding='max_length', max_length=self.max_len,
                                  return_tensors='pt')
        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': torch.tensor(label, dtype=torch.long)
        }


# ------------------------------------------------------------
# 6. ПОСТРОЕНИЕ MAP ИНТЕНТ -> ОТВЕТ НА ОСНОВЕ CSV
# ------------------------------------------------------------
def build_intent_to_response(csv_questions, qa_dict):
    """
    Для каждого интента собирает ответы из CSV, соответствующие вопросам этого интента,
    и выбирает наиболее подходящий ответ (первый по частоте или самый длинный).
    """
    intent_to_responses = defaultdict(list)
    for q in csv_questions:
        intent = get_intent_by_keywords(q)
        if intent != -1 and q in qa_dict:
            intent_to_responses[intent].append(qa_dict[q])

    intent_to_response = {}
    for intent, responses in intent_to_responses.items():
        # Выбираем самый частый ответ; если все уникальны, берём первый
        counter = Counter(responses)
        most_common = counter.most_common(1)[0][0]
        intent_to_response[str(intent)] = most_common
    return intent_to_response


# ------------------------------------------------------------
# 7. ОБУЧЕНИЕ И ОЦЕНКА (расширенная версия)
# ------------------------------------------------------------
def train_and_evaluate():
    # Загружаем вопросы и ответы из CSV
    csv_questions, qa_dict = load_csv_qa("university.csv")
    if not csv_questions:
        print("⚠️ Не удалось загрузить вопросы из CSV. Обучение будет только на шаблонах и приложении.")

    # Генерация всех примеров
    examples = generate_all_examples(csv_questions)
    texts = [ex[0] for ex in examples]
    labels = [ex[1] for ex in examples]

    # Разделение на train/val
    X_train, X_val, y_train, y_val = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )
    print(f"📊 Train: {len(X_train)}, Val: {len(X_val)}")

    # Модель и токенизатор
    model_name = "cointegrated/rubert-tiny2"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=len(INTENTS), ignore_mismatched_sizes=True
    )

    train_dataset = IntentDataset(X_train, y_train, tokenizer) # Датасет для тренировочных данных
    val_dataset = IntentDataset(X_val, y_val, tokenizer) # Датасет для валидационной выборки

    training_args = TrainingArguments(
        output_dir="./rubert_intent_model", # Папка, куда будут сохраняться чекпоинты модели и результат
        num_train_epochs=10, # Количество полных проходов по всему тренировочному датасету
        per_device_train_batch_size=16, # Размер батча на одно устройство (GPU/CPU) при обучении
        per_device_eval_batch_size=32, # Размер батча при валидации
        warmup_steps=50, # Количество шагов, за которое скорость обучения линейно увеличивается
        weight_decay=0.01,# Коэффициент регуляризации L2
        logging_steps=10, # Через сколько шагов логировать метрики
        eval_strategy="epoch", # Стратегия валидации
        save_strategy="epoch", # Стратегия сохранения чекпоинтов
        load_best_model_at_end=True,  # По окончании обучения загрузить модель с лучшим значением
        metric_for_best_model="accuracy", # Какая метрика считается лучшей при выборе модели (accuracy)
        fp16=False,
        report_to="none", # Куда отправлять логи (wandb, tensorboard). "none" — никуда.
    )

    def compute_metrics(eval_pred):
        preds = np.argmax(eval_pred.predictions, axis=1)
        return {"accuracy": accuracy_score(eval_pred.label_ids, preds)}

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],
    )

    print("🚀 Начинаем обучение...")
    trainer.train()

    # Оценка
    val_metrics = trainer.evaluate()
    print(f"\n🎯 Точность на валидации: {val_metrics['eval_accuracy']:.4f}")

    predictions = trainer.predict(val_dataset)
    pred_labels = np.argmax(predictions.predictions, axis=1)
    print("\n📋 Classification Report:")
    print(classification_report(y_val, pred_labels, target_names=[INTENTS[i]['name'] for i in range(len(INTENTS))]))

    # Матрица ошибок
    cm = confusion_matrix(y_val, pred_labels)
    plt.figure(figsize=(10, 8))
    plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
    plt.title("Confusion Matrix")
    plt.colorbar()
    tick_marks = np.arange(len(INTENTS))
    plt.xticks(tick_marks, [INTENTS[i]['name'] for i in range(len(INTENTS))], rotation=45, ha='right')
    plt.yticks(tick_marks, [INTENTS[i]['name'] for i in range(len(INTENTS))])
    plt.ylabel('True label')
    plt.xlabel('Predicted label')
    plt.tight_layout()
    plt.savefig("confusion_matrix.png")
    plt.show()

    # Сохраняем модель
    model.save_pretrained("./rubert_intent_model_final")
    tokenizer.save_pretrained("./rubert_intent_model_final")

    # Создаём маппинг интент -> ответ (используя реальные ответы из CSV)
    if csv_questions and qa_dict:
        intent_to_response = build_intent_to_response(csv_questions, qa_dict)
        # Добавляем ответы для интентов, которых нет в CSV (заглушки)
        for i in range(len(INTENTS)):
            if str(i) not in intent_to_response:
                intent_to_response[str(i)] = f"Ответ для интента {INTENTS[i]['name']} (нет в CSV)"
    else:
        intent_to_response = {str(i): f"Ответ для интента {INTENTS[i]['name']}" for i in INTENTS}

    with open("intent_mapping.json", "w", encoding="utf-8") as f:
        json.dump(intent_to_response, f, ensure_ascii=False, indent=2)

    print("✅ Модель сохранена в ./rubert_intent_model_final")
    print("📄 intent_mapping.json создан с реальными ответами из CSV (где возможно).")
    print("📊 Матрица ошибок сохранена как confusion_matrix.png")

    return model, tokenizer, val_metrics['eval_accuracy']


# Запуск
if __name__ == "__main__":
    model, tokenizer, accuracy = train_and_evaluate()
    print(f"\n🎉 Итоговая точность: {accuracy:.4f}")