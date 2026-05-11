import telebot
import google.generativeai as genai
import pandas as pd
import yfinance as yf
from io import BytesIO
import matplotlib.pyplot as plt
from flask import Flask
from threading import Thread
import os

# --- TẠO CỔNG GIẢ ĐỂ RENDER KHÔNG BÁO LỖI ---
app = Flask('')
@app.route('/')
def home(): return "Bot is running!"

def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- CẤU HÌNH API ---
BOT_TOKEN = "8672499282:AAFNmrEg1Ff625fPuKYu7xuNXIVRehAoq1E"
GEMINI_KEY = "AIzaSyD0hw6_QhRUQiBY72ouaoVrjOJRTHOylTg"

bot = telebot.TeleBot(BOT_TOKEN)
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def get_ou_analysis(ticker):
    try:
        df = yf.download(ticker, period="1mo", interval="1h", progress=False, auto_adjust=True)
        if df.empty: return None, None
        window = 24 
        df['mu'] = df['Close'].rolling(window=window).mean()
        df['sigma'] = df['Close'].rolling(window=window).std()
        df['z_score'] = (df['Close'] - df['mu']) / df['sigma']
        current_z = df['z_score'].iloc[-1]
        plt.figure(figsize=(10, 5))
        plt.plot(df.index, df['z_score'], color='#8e44ad')
        plt.axhline(y=2, color='#e74c3c', linestyle='--')
        plt.axhline(y=-2, color='#2ecc71', linestyle='--')
        plt.title(f"OU Mean Reversion - {ticker}")
        img_buf = BytesIO()
        plt.savefig(img_buf, format='png')
        img_buf.seek(0)
        plt.close()
        return current_z, img_buf
    except: return None, None

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "✅ Trạm điều khiển đã Online! Gõ /gold để check biên độ.")

@bot.message_handler(commands=['gold'])
def check_gold(message):
    bot.send_message(message.chat.id, "⌛ Đang tính toán...")
    z, img = get_ou_analysis("GC=F") 
    if z is not None:
        bot.send_photo(message.chat.id, img, caption=f"📊 Z-Score Vàng: `{z:.2f}`")
    else:
        bot.reply_to(message, "❌ Lỗi lấy dữ liệu.")

if __name__ == "__main__":
    keep_alive() # Kích hoạt cổng giả
    print("Bot đang chạy...")
    bot.infinity_polling()
