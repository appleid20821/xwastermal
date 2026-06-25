from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import paramiko
import asyncio
import threading

app = FastAPI()

# مشخصات سرور اصلی لینوکس شما
VPS_IP = "45.84.88.133"
SSH_PORT = 22
SSH_USER = "root"
SSH_PASS = "Aa12341234"  # اگر پسورد روت در بیت‌وایز عدد دیگری بود، دقیقاً همان را اینجا بگذار

html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Wasmer Web Terminal</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css" />
    <script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js"></script>
    <style>
        body { background-color: #1a1a1a; margin: 20px; font-family: monospace; }
        #terminal { width: 100%; height: 80vh; }
    </style>
</head>
<body>
    <h2 style="color: #00ff00; text-align: center;">Morteza's Secure Web Terminal via Wasmer</h2>
    <div id="terminal"></div>

    <script>
        const term = new Terminal({
            cursorBlink: true,
            theme: { background: '#000000', foreground: '#00ff00' },
            convertEol: true  // اصلاح فرمت خطوط در سیستم‌عامل‌های مختلف
        });
        term.open(document.getElementById('terminal'));
        term.writeln('Connecting to Wasmer Bridge...');

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${protocol}//${window.location.host}/ws-terminal`);

        ws.onopen = () => {
            term.writeln('Wasmer Bridge Connected! Authenticating with VPS SSH...');
        };

        ws.onmessage = (event) => {
            term.write(event.data);
        };

        ws.onclose = () => {
            term.writeln('\\r\\n[System] Terminal Connection Closed.');
        };

        term.onData(data => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(data);
            }
        });
    </script>
</body>
</html>
"""

@app.get("/")
async def get_terminal():
    return HTMLResponse(content=html_content)

@app.websocket("/ws-terminal")
async def ws_terminal(websocket: WebSocket):
    await websocket.accept()
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        # بهینه‌سازی پارامترهای اتصال برای رد کردن سریع بنر اولیه SSH
        ssh.connect(
            VPS_IP, 
            port=SSH_PORT, 
            username=SSH_USER, 
            password=SSH_PASS, 
            timeout=10,
            look_for_keys=False,      # غیرفعال کردن جستجوی کلیدهای محلی
            allow_agent=False         # غیرفعال کردن SSH Agent خارجی
        )
        # ایجاد یک ترمینال مجازی استاندارد با ابعاد مشخص
        chan = ssh.invoke_shell(term='xterm', width=80, height=24)
        # یک پیام اولیه برای تایید باز شدن لوله ارسال می‌کنیم
        await websocket.send_text("--- Shell Session Started ---\\r\\n")
    except Exception as e:
        error_msg = f"\\r\\n\\u001b[31m[SSH Connection Failed]: {str(e)}\\u001b[0m\\r\\n"
        await websocket.send_text(error_msg)
        await websocket.close()
        return

    loop = asyncio.get_event_loop()

    # خواندن بلادرنگ پاسخ‌ها از ترمینال سرور
    def ssh_to_ws():
        while True:
            try:
                # استفاده از بلاک چنل برای خواندن بدون وقفه داده‌ها
                if chan.recv_ready():
                    data = chan.recv(4096)
                    if not data:
                        break
                    # تبدیل بایت‌ها به متنی که xterm بفهمد
                    text_data = data.decode('utf-8', errors='ignore')
                    asyncio.run_coroutine_threadsafe(websocket.send_text(text_data), loop)
                else:
                    # یک وقفه بسیار کوتاه برای جلوگیری از اشغال ۱۰۰ درصدی CPU Thread
                    import time
                    time.sleep(0.01)
            except Exception:
                break

    threading.Thread(target=ssh_to_ws, daemon=True).start()

    # دریافت کلیدها از مرورگر و فرستادن مستقیم به لینوکس
    try:
        while True:
            data = await websocket.receive_text()
            if chan.send_ready():
                chan.send(data)
    except Exception:
        pass
    finally:
        chan.close()
        ssh.close()
