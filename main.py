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
SSH_PASS = "1"  # پسورد روت سرورت را اینجا دقیق وارد کن

# طراحی رابط کاربری ترمینال در مرورگر با استفاده از Xterm.js
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
            theme: { background: '#000000', foreground: '#00ff00' }
        });
        term.open(document.getElementById('terminal'));
        term.writeln('Connecting to Wasmer Bridge...');

        // ایجاد اتصال وب‌ساکت زنده به پایتون
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${protocol}//${window.location.host}/ws-terminal`);

        ws.onopen = () => {
            term.writeln('Wasmer Bridge Connected! Opening SSH Tunnel to VPS...\\r\\n');
        };

        ws.onmessage = (event) => {
            term.write(event.data);
        };

        ws.onclose = () => {
            term.writeln('\\r\\nConnection closed.');
        };

        // فرستادن کلیدهای فشرده شده در کیبورد به سرور
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
    
    # ایجاد کلاینت SSH با Paramiko
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(VPS_IP, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=10)
        # باز کردن یک شل تعاملی (Interactive Shell) مثل محیط ترمینال واقعی
        chan = ssh.invoke_shell(term='xterm')
    except Exception as e:
        await websocket.send_text(f"SSH Connection Failed: {str(e)}\r\n")
        await websocket.close()
        return

    loop = asyncio.get_event_loop()

    # تابع خواندن داده از SSH و فرستادن به مرورگر
    def ssh_to_ws():
        while True:
            try:
                if chan.recv_ready():
                    data = chan.recv(4096).decode('utf-8', errors='ignore')
                    asyncio.run_coroutine_threadsafe(websocket.send_text(data), loop)
            except Exception:
                break

    threading.Thread(target=ssh_to_ws, daemon=True).start()

    # دریافت کلیدهای کیبورد از مرورگر و نوشتن روی ترمینال SSH
    try:
        while True:
            data = await websocket.receive_text()
            chan.send(data)
    except Exception:
        pass
    finally:
        chan.close()
        ssh.close()
