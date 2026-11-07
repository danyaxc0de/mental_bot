import telebot
from telebot import types
import sqlite3
import os
from flask import Flask
from threading import Thread

# === НАСТРОЙКИ ===
TOKEN = "8200228343:AAHdL83_SmYH2awPxmA0uu20vESfKVnskZ0"
ADMIN_ID = 8192413936
bot = telebot.TeleBot(TOKEN)

# === ВЕБ-СЕРВЕР ДЛЯ RENDER ===
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is alive"
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
def keep_alive(): Thread(target=run_flask).start()

# === БАЗА ===
conn = sqlite3.connect('mental_test.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, gems INTEGER DEFAULT 2, ref_id INTEGER DEFAULT 0)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS rooms 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, creator_id INTEGER, num_questions INTEGER, status TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS answers 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, room_id INTEGER, user_id INTEGER, answers_json TEXT)''')
conn.commit()

QUESTIONS_BANK = [
    ("Что ты выберешь?", "☕ Кофе", "🍵 Чай"),
    ("Где бы ты хотел жить?", "🌊 Море", "🏔 Горы"),
    ("Кто тебе ближе?", "🐈 Кошки", "🐕 Собаки"),
    ("Вечер пятницы?", "🎉 Вечеринка", "🛌 Дома"),
    ("Как принимаешь решения?", "❤️ Сердцем", "🧠 Головой"),
    ("Что важнее?", "💼 Карьера", "👨‍👩‍👧 Семья"),
    ("Твой стиль?", "👟 Кроссовки", "👞 Туфли"),
    ("Что смотришь?", "🎬 Кино", "📺 Сериалы"),
    ("Как отдыхаешь?", "🏃‍♂️ Активно", "🛋 Пассивно"),
    ("Твой транспорт?", "🚗 Машина", "🚌 Общественный"),
    ("Что выберешь на завтрак?", "🥞 Сладкое", "🍳 Соленое"),
    ("Как относишься к риску?", "🎲 Азарт", "🛡 Осторожность"),
    ("Твой стиль общения?", "🗣 Громкий", "🤫 Тихий"),
    ("Что выберешь в отпуск?", "🏕 Природа", "🏙 Город"),
    ("Твой идеальный вечер?", "📖 Книга", "🎮 Игры"),
]

def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🔗 Создать тест", callback_data="create_room"),
        types.InlineKeyboardButton("💎 Мои гемы / Купить", callback_data="shop"),
        types.InlineKeyboardButton("👥 Позвать друга (+1 💎)", callback_data="get_ref")
    )
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id, gems) VALUES (?, 2)", (user_id,))
        conn.commit()

    args = message.text.split()
    if len(args) > 1:
        try:
            referrer_id = int(args[1])
            if referrer_id != user_id:
                cursor.execute("SELECT ref_id FROM users WHERE user_id = ?", (user_id,))
                if cursor.fetchone()[0] == 0:
                    cursor.execute("UPDATE users SET ref_id = ?, gems = gems + 1 WHERE user_id = ?", (referrer_id, user_id))
                    cursor.execute("UPDATE users SET gems = gems + 1 WHERE user_id = ?", (referrer_id,))
                    conn.commit()
                    bot.send_message(referrer_id, "🎉 По твоей ссылке пришел друг! +1 💎 гем.")
        except:
            pass

    cursor.execute("SELECT gems FROM users WHERE user_id = ?", (user_id,))
    gems = cursor.fetchone()[0]
    bot.send_message(user_id, f"👋 Привет! Это бот для проверки ментальной связи.\n\nУ тебя на балансе: **{gems} 💎 гемов**.\nДля создания теста нужно 3 💎. Пригласи друга по кнопке ниже, чтобы получить +1 💎!", parse_mode="Markdown", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "create_room")
def choose_length(call):
    user_id = call.from_user.id
    cursor.execute("SELECT gems FROM users WHERE user_id = ?", (user_id,))
    gems = cursor.fetchone()[0]
    
    if gems < 3:
        bot.answer_callback_query(call.id, "❌ Недостаточно гемов! Нужно 3 💎.\nПригласи друга или купи гемы.", show_alert=True)
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for i in range(3, 16):
        markup.add(types.InlineKeyboardButton(f"{i} вопросов (3 💎)", callback_data=f"len_{i}"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back"))
    
    bot.send_message(user_id, "Выбери количество вопросов (от 3 до 15):", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("len_"))
def create_room(call):
    length = int(call.data.split("_")[1])
    user_id = call.from_user.id
    
    cursor.execute("SELECT gems FROM users WHERE user_id = ?", (user_id,))
    gems = cursor.fetchone()[0]
    
    if gems < 3:
        bot.answer_callback_query(call.id, "❌ Недостаточно гемов!", show_alert=True)
        return
    
    cursor.execute("UPDATE users SET gems = gems - 3 WHERE user_id = ?", (user_id,))
    conn.commit()
    
    cursor.execute("INSERT INTO rooms (creator_id, num_questions, status) VALUES (?, ?, ?)", (user_id, length, 'waiting'))
    conn.commit()
    room_id = cursor.lastrowid
    
    bot_username = bot.get_me().username
    link = f"https://t.me/{bot_username}?start={room_id}"
    
    bot.answer_callback_query(call.id, "Списано 3 💎. Тест создан!", show_alert=True)
    text = (
        f"🔗 **Твой тест на {length} вопросов создан!**\n\n"
        f"Отправь эту ссылку другу:\n`{link}`\n\n"
        f"Сам ответь на вопросы здесь (нажми кнопку ниже)."
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✍️ Пройти свой тест", callback_data=f"start_self_{room_id}"))
    bot.send_message(user_id, text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("start_self_"))
def start_self(call):
    room_id = int(call.data.split("_")[2])
    bot.answer_callback_query(call.id)
    start_quiz(call.from_user.id, room_id, 0, [])

def start_quiz(user_id, room_id, q_index, answers):
    cursor.execute("SELECT num_questions FROM rooms WHERE id = ?", (room_id,))
    total_q = cursor.fetchone()[0]

    if q_index >= total_q:
        answers_json = str(answers)
        cursor.execute("INSERT INTO answers (room_id, user_id, answers_json) VALUES (?, ?, ?)", (room_id, user_id, answers_json))
        conn.commit()
        
        cursor.execute("SELECT user_id, answers_json FROM answers WHERE room_id = ?", (room_id,))
        all_answers = cursor.fetchall()
        
        if len(all_answers) >= 2:
            cursor.execute("UPDATE rooms SET status = 'completed' WHERE id = ?", (room_id,))
            conn.commit()
            
            creator_id = cursor.execute("SELECT creator_id FROM rooms WHERE id = ?", (room_id,)).fetchone()[0]
            creator_ans, guest_ans = [], []
            for u_id, ans in all_answers:
                if u_id == creator_id: creator_ans = eval(ans)
                else: guest_ans = eval(ans)
            
            matches = sum(1 for i in range(total_q) if creator_ans[i] == guest_ans[i])
            percent = int((matches / total_q) * 100)
            
            result_text = f"🧠 **Ваша ментальная связь:** {percent}%\n\nВы совпали в {matches} из {total_q} вопросов."
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔍 Подробности (3 💎)", callback_data=f"details_{room_id}"))
            
            bot.send_message(creator_id, result_text, parse_mode="Markdown", reply_markup=markup)
            bot.send_message(user_id, result_text, parse_mode="Markdown", reply_markup=markup)
            return
        else:
            bot.send_message(user_id, "✅ Ты прошел тест! Ждем второго человека...")
            return

    q_data = QUESTIONS_BANK[q_index % len(QUESTIONS_BANK)]
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(q_data[1], callback_data=f"ans_{q_index}_{q_data[1]}"),
        types.InlineKeyboardButton(q_data[2], callback_data=f"ans_{q_index}_{q_data[2]}")
    )
    bot.send_message(user_id, f"Вопрос {q_index+1} из {total_q}:\n**{q_data[0]}**", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("ans_"))
def process_answer(call):
    data = call.data.split("_")
    q_index = int(data[1])
    answer = data[2]
    user_id = call.from_user.id
    
    cursor.execute("SELECT id, num_questions FROM rooms WHERE creator_id = ? AND status = 'waiting' ORDER BY id DESC LIMIT 1", (user_id,))
    room = cursor.fetchone()
    
    if not room:
        cursor.execute("SELECT room_id FROM answers WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,))
        res = cursor.fetchone()
        if res:
            room_id = res[0]
            cursor.execute("SELECT num_questions FROM rooms WHERE id = ?", (room_id,))
            total_q = cursor.fetchone()[0]
            room = (room_id, total_q)
    
    if room:
        room_id, total_q = room
        bot.answer_callback_query(call.id, "Ответ принят!")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        
        global temp_answers
        if user_id not in temp_answers: temp_answers[user_id] = []
        temp_answers[user_id].append(answer)
        
        if len(temp_answers[user_id]) < total_q:
            start_quiz(user_id, room_id, len(temp_answers[user_id]), temp_answers[user_id])
        else:
            cursor.execute("INSERT INTO answers (room_id, user_id, answers_json) VALUES (?, ?, ?)", (room_id, user_id, str(temp_answers[user_id])))
            conn.commit()
            
            cursor.execute("SELECT user_id FROM answers WHERE room_id = ?", (room_id,))
            all_ans = cursor.fetchall()
            if len(all_ans) >= 2:
                cursor.execute("UPDATE rooms SET status = 'completed' WHERE id = ?", (room_id,))
                conn.commit()
                
                cursor.execute("SELECT user_id, answers_json FROM answers WHERE room_id = ?", (room_id,))
                answers_db = cursor.fetchall()
                creator_id = cursor.execute("SELECT creator_id FROM rooms WHERE id = ?", (room_id,)).fetchone()[0]
                
                creator_ans, guest_ans = [], []
                for u_id, ans in answers_db:
                    if u_id == creator_id: creator_ans = eval(ans)
                    else: guest_ans = eval(ans)
                
                matches = sum(1 for i in range(total_q) if creator_ans[i] == guest_ans[i])
                percent = int((matches / total_q) * 100)
                
                result_text = f"🧠 **Ваша ментальная связь:** {percent}%\n\nВы совпали в {matches} из {total_q} вопросов."
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔍 Подробности (3 💎)", callback_data=f"details_{room_id}"))
                
                bot.send_message(creator_id, result_text, parse_mode="Markdown", reply_markup=markup)
                bot.send_message(user_id, result_text, parse_mode="Markdown", reply_markup=markup)
            else:
                bot.send_message(user_id, "✅ Ты прошел тест! Ждем второго человека...")

@bot.callback_query_handler(func=lambda call: call.data.startswith("details_"))
def details(call):
    room_id = int(call.data.split("_")[1])
    user_id = call.from_user.id
    cursor.execute("SELECT gems FROM users WHERE user_id = ?", (user_id,))
    gems = cursor.fetchone()[0]
    
    if gems < 3:
        bot.answer_callback_query(call.id, "Недостаточно гемов! Нужно 3 💎.", show_alert=True)
        return
    
    cursor.execute("UPDATE users SET gems = gems - 3 WHERE user_id = ?", (user_id,))
    conn.commit()
    
    cursor.execute("SELECT creator_id FROM rooms WHERE id = ?", (room_id,))
    creator_id = cursor.fetchone()[0]
    cursor.execute("SELECT user_id, answers_json FROM answers WHERE room_id = ?", (room_id,))
    answers_db = cursor.fetchall()
    cursor.execute("SELECT num_questions FROM rooms WHERE id = ?", (room_id,))
    total_q = cursor.fetchone()[0]
    
    creator_ans, guest_ans = [], []
    for u_id, ans in answers_db:
        if u_id == creator_id: creator_ans = eval(ans)
        else: guest_ans = eval(ans)
        
    details_text = "🔍 **Подробности:**\n\n"
    for i in range(total_q):
        if creator_ans[i] == guest_ans[i]:
            details_text += f"✅ Совпали: {creator_ans[i]}\n"
        else:
            details_text += f"❌ Разногласие: Ты — '{creator_ans[i]}', он/она — '{guest_ans[i]}'\n"
    
    bot.send_message(user_id, details_text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "shop")
def shop(call):
    user_id = call.from_user.id
    cursor.execute("SELECT gems FROM users WHERE user_id = ?", (user_id,))
    balance = cursor.fetchone()[0]
    text = f"💎 **Баланс: {balance} гемов**\n\nКупить гемы:"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Купить 10 гемов (10 ⭐)", callback_data="buy_gems_10"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back"))
    bot.send_message(user_id, text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "get_ref")
def get_ref(call):
    bot_username = bot.get_me().username
    link = f"https://t.me/{bot_username}?start={call.from_user.id}"
    bot.send_message(call.from_user.id, f"🔗 **Твоя ссылка:**\n\n`{link}`\n\nЗа каждого друга +1 💎 гем.", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "buy_gems_10")
def buy_gems(call):
    prices = [types.LabeledPrice(label="10 Гемов", amount=10)]
    try:
        bot.send_invoice(call.from_user.id, "Покупка 10 Гемов", "Пополнение баланса.", "gems_10", "", "XTR", prices)
    except Exception as e:
        bot.send_message(call.from_user.id, f"Ошибка: {e}")

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    if message.successful_payment.invoice_payload == "gems_10":
        cursor.execute("UPDATE users SET gems = gems + 10 WHERE user_id = ?", (message.from_user.id,))
        conn.commit()
        bot.send_message(message.from_user.id, "✅ +10 💎 гемов!")

@bot.callback_query_handler(func=lambda call: call.data == "back")
def back(call): bot.send_message(call.from_user.id, "Меню:", reply_markup=main_menu())

temp_answers = {}

if __name__ == '__main__':
    keep_alive()
    print("Бот запущен...")
    bot.infinity_polling()
