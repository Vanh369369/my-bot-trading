import telebot
import google.generativeai as genai
import pandas as pd
import numpy as np
import yfinance as yf
from io import BytesIO
import matplotlib
matplotlib.use('Agg')  # FIX: Colab không có display, phải dùng backend này
import matplotlib.pyplot as plt
import time
import threading

# --- CẤU HÌNH API ---
BOT_TOKEN = "YOUR_BOT_TOKEN"
GEMINI_KEY = "YOUR_GEMINI_KEY"

# Khởi tạo hệ thống
bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)
genai.configure(api_key=GEMINI_KEY)

# FIX: Dùng model mới nhất, tên cũ có thể đã bị deprecated
model = genai.GenerativeModel('gemini-2.0-flash')

# --- HÀM TÍNH TOÁN BIÊN ĐỘ VÀNG (OU MODEL) ---
def get_ou_analysis(ticker):
    try:
        df = yf.download(ticker, period="1mo", interval="1h", progress=False, auto_adjust=True)
        if df.empty:
            return None, None

        # FIX: yfinance mới trả về MultiIndex columns, cần flatten
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Đảm bảo cột Close tồn tại
        if 'Close' not in df.columns:
            print(f"Columns hiện có: {df.columns.tolist()}")
            return None, None

        df = df.dropna(subset=['Close'])

        window = 24
        df['mu'] = df['Close'].rolling(window=window).mean()
        df['sigma'] = df['Close'].rolling(window=window).std()
        df['z_score'] = (df['Close'] - df['mu']) / df['sigma']
        df = df.dropna(subset=['z_score'])

        if df.empty:
            return None, None

        current_z = float(df['z_score'].iloc[-1])  # FIX: ép kiểu tránh lỗi Series

        # Vẽ biểu đồ
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(df.index, df['z_score'], color='#8e44ad', label='Z-Score')
        ax.axhline(y=2,  color='#e74c3c', linestyle='--', label='Overbought (Sell)')
        ax.axhline(y=-2, color='#2ecc71', linestyle='--', label='Oversold (Buy)')
        ax.axhline(y=0,  color='gray', alpha=0.5)
        ax.set_title(f"OU Mean Reversion Indicator - {ticker}")
        ax.legend()
        plt.tight_layout()

        img_buf = BytesIO()
        fig.savefig(img_buf, format='png', dpi=100)
        img_buf.seek(0)
        plt.close(fig)

        return current_z, img_buf

    except Exception as e:
        print(f"Lỗi get_ou_analysis: {e}")
        return None, None


# --- HÀM GỌI GEMINI AN TOÀN ---
def ask_gemini(prompt_text, image_data=None):
    """Gọi Gemini với xử lý lỗi đầy đủ"""
    try:
        if image_data:
            img_part = {"mime_type": "image/jpeg", "data": image_data}
            response = model.generate_content([prompt_text, img_part])
        else:
            response = model.generate_content(prompt_text)

        # FIX: Kiểm tra response bị block bởi safety filter
        if not response.candidates:
            return "⚠️ Gemini không thể trả lời câu này (bị lọc nội dung)."

        # FIX: Trích xuất text an toàn
        if response.text:
            return response.text
        else:
            return "⚠️ Gemini trả về phản hồi trống."

    except Exception as e:
        print(f"Lỗi Gemini: {e}")
        return f"❌ Lỗi khi gọi Gemini: {str(e)}"


# --- CÁC LỆNH ĐIỀU KHIỂN ---

@bot.message_handler(commands=['start'])
def start(message):
    welcome_text = (
        "📊 *TRẠM ĐIỀU KHIỂN LOGISTICS & TRADING*\n\n"
        "Chào Boss\\! Tôi đã sẵn sàng hỗ trợ trên điện thoại:\n"
        "1️⃣ Gửi tin nhắn thường để hỏi Gemini \\(Code, Bát tự, Logistics\\.\\.\\.\\)\n"
        "2️⃣ Gõ /gold để check biên độ Vàng theo mô hình OU\\.\n"
        "3️⃣ Chụp ảnh chứng từ gửi vào đây để tôi bóc tách dữ liệu\\.\n"
    )
    # FIX: Dùng MarkdownV2 hoặc bỏ parse_mode để tránh lỗi formatting
    try:
        bot.reply_to(message, welcome_text, parse_mode="MarkdownV2")
    except Exception:
        bot.reply_to(message, "📊 Bot đã sẵn sàng!\nDùng /gold để phân tích vàng.\nGửi ảnh chứng từ để bóc tách.\nHoặc hỏi bất cứ điều gì!")


@bot.message_handler(commands=['gold'])
def check_gold(message):
    bot.send_message(message.chat.id, "⌛ Đang quét dữ liệu sàn thế giới và tính toán biên độ...")
    
    z, img = get_ou_analysis("GC=F")
    
    if z is not None and img is not None:
        if z > 2:
            status = "🔴 CẢNH BÁO: QUÁ MUA — Canh đảo chiều Giảm"
        elif z < -2:
            status = "🟢 CẢNH BÁO: QUÁ BÁN — Canh đảo chiều Tăng"
        else:
            status = "⚪ TRẠNG THÁI: GIÁ ĐANG ỔN ĐỊNH"

        caption = (
            f"📌 PHÂN TÍCH VÀNG (XAUUSD)\n\n"
            f"Z-Score hiện tại: {z:.2f}\n"
            f"{status}"
        )
        # FIX: Không dùng parse_mode với caption có ký tự đặc biệt
        bot.send_photo(message.chat.id, img, caption=caption)
    else:
        bot.reply_to(message, "❌ Không lấy được dữ liệu. Kiểm tra lại kết nối mạng hoặc ticker.")


@bot.message_handler(content_types=['photo'])
def handle_docs(message):
    bot.reply_to(message, "🔍 Đang dùng Gemini AI đọc và bóc tách thông tin chứng từ...")
    try:
        # Lấy ảnh chất lượng cao nhất
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        prompt = (
            "Bạn là chuyên gia Logistics. Hãy đọc ảnh này và liệt kê chi tiết: "
            "Tên hàng, Số lượng, Trọng lượng, Số Container/Bill, và mã HS code nếu thấy. "
            "Trình bày rõ ràng theo từng mục."
        )

        result = ask_gemini(prompt, image_data=downloaded_file)
        
        # FIX: Tách tin nhắn dài thành nhiều phần nếu vượt giới hạn Telegram (4096 ký tự)
        if len(result) > 4000:
            for i in range(0, len(result), 4000):
                bot.send_message(message.chat.id, result[i:i+4000])
        else:
            bot.reply_to(message, f"📋 KẾT QUẢ BÓC TÁCH:\n\n{result}")

    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi xử lý ảnh: {str(e)}")


@bot.message_handler(func=lambda message: True)
def chat_with_gemini(message):
    try:
        # FIX: Thêm typing action để user biết bot đang xử lý
        bot.send_chat_action(message.chat.id, 'typing')
        
        result = ask_gemini(message.text)
        
        # FIX: Tách tin nhắn dài
        if len(result) > 4000:
            for i in range(0, len(result), 4000):
                bot.send_message(message.chat.id, result[i:i+4000])
        else:
            bot.reply_to(message, result)

    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {str(e)}")


# --- CHẠY BOT TRÊN GOOGLE COLAB ---
# FIX: Dùng threaded=True và restart khi gặp lỗi kết nối
def run_bot():
    print("✅ Bot đang chạy... Gửi /start vào Telegram để kiểm tra!")
    while True:
        try:
            bot.infinity_polling(
                timeout=60,           # FIX: Timeout cho mỗi request
                long_polling_timeout=30,
                restart_on_change=False,
                none_stop=True        # Tiếp tục dù có lỗi nhỏ
            )
        except Exception as e:
            print(f"⚠️ Polling bị ngắt: {e} — Đang khởi động lại sau 5 giây...")
            time.sleep(5)

# Chạy trong thread riêng để Colab không bị block
bot_thread = threading.Thread(target=run_bot, daemon=True)
bot_thread.start()

# FIX: Giữ Colab cell chạy liên tục (không bị timeout)
print("🔄 Keep-alive đang chạy. Đừng tắt cell này!")
while True:
    time.sleep(60)
    print("💓 Bot vẫn đang hoạt động...")
