import telebot
import google.generativeai as genai
import pandas as pd
import numpy as np
import yfinance as yf
from io import BytesIO
import matplotlib.pyplot as plt

# --- CẤU HÌNH API ---
BOT_TOKEN = "8672499282:AAFNmrEg1Ff625fPuKYu7xuNXIVRehAoq1E"
GEMINI_KEY = "AIzaSyD0hw6_QhRUQiBY72ouaoVrjOJRTHOylTg"

# Khởi tạo hệ thống
bot = telebot.TeleBot(BOT_TOKEN)
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- HÀM TÍNH TOÁN BIÊN ĐỘ VÀNG (OU MODEL) ---
def get_ou_analysis(ticker):
    try:
        # Lấy dữ liệu Vàng 1 tháng gần nhất, khung 1h
        df = yf.download(ticker, period="1mo", interval="1h", progress=False, auto_adjust=True)
        if df.empty: return None, None
        
        # Tính toán Z-Score (Dựa trên Mean Reversion)
        window = 24 
        df['mu'] = df['Close'].rolling(window=window).mean()
        df['sigma'] = df['Close'].rolling(window=window).std()
        df['z_score'] = (df['Close'] - df['mu']) / df['sigma']
        
        current_z = df['z_score'].iloc[-1]
        
        # Vẽ biểu đồ
        plt.figure(figsize=(10, 5))
        plt.plot(df.index, df['z_score'], color='#8e44ad', label='Z-Score')
        plt.axhline(y=2, color='#e74c3c', linestyle='--', label='Overbought (Sell)')
        plt.axhline(y=-2, color='#2ecc71', linestyle='--', label='Oversold (Buy)')
        plt.axhline(y=0, color='gray', alpha=0.5)
        plt.title(f"OU Mean Reversion Indicator - {ticker}")
        plt.legend()
        
        img_buf = BytesIO()
        plt.savefig(img_buf, format='png')
        img_buf.seek(0)
        plt.close()
        
        return current_z, img_buf
    except Exception as e:
        print(f"Lỗi: {e}")
        return None, None

# --- CÁC LỆNH ĐIỀU KHIỂN ---

@bot.message_handler(commands=['start'])
def start(message):
    welcome_text = (
        "📊 **TRẠM ĐIỀU KHIỂN LOGISTICS & TRADING**\n\n"
        "Chào Boss! Hệ thống đã kích hoạt thành công:\n"
        "1️⃣ Gửi tin nhắn thường để hỏi Gemini (Code, Bát tự, Logistics...)\n"
        "2️⃣ Gõ /gold để check biên độ Vàng theo mô hình OU.\n"
        "3️⃣ Chụp ảnh chứng từ gửi vào đây để tôi bóc tách dữ liệu."
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

@bot.message_handler(commands=['gold'])
def check_gold(message):
    bot.send_message(message.chat.id, "⌛ Đang tính toán biên độ Vàng...")
    z, img = get_ou_analysis("GC=F") 
    if z is not None:
        status = "🔴 QUÁ MUA (Canh Sell)" if z > 2 else "🟢 QUÁ BÁN (Canh Buy)" if z < -2 else "⚪ BÌNH THƯỜNG"
        bot.send_photo(
            message.chat.id, 
            img, 
            caption=f"📌 **PHÂN TÍCH VÀNG (XAUUSD)**\n- Z-Score: `{z:.2f}`\n- Trạng thái: {status}",
            parse_mode="Markdown"
        )
    else:
        bot.reply_to(message, "❌ Lỗi lấy dữ liệu.")

@bot.message_handler(content_types=['photo'])
def handle_docs(message):
    bot.reply_to(message, "🔍 Đang dùng Gemini AI đọc chứng từ...")
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        img_part = {"mime_type": "image/jpeg", "data": downloaded_file}
        prompt = "Đọc ảnh chứng từ này và tóm tắt: Tên hàng, Số lượng, Trọng lượng, số Cont/Bill, mã HS Code."
        response = model.generate_content([prompt, img_part])
        bot.reply_to(message, f"📋 **KẾT QUẢ:**\n\n{response.text}", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")

@bot.message_handler(func=lambda message: True)
def chat_with_gemini(message):
    try:
        response = model.generate_content(message.text)
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, "Đã xảy ra lỗi khi kết nối với AI.")

if __name__ == "__main__":
    print("Bot đang chạy...")
    bot.infinity_polling()
