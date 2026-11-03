# -*- coding: utf-8 -*-
"""手机扫码查看.py —— 一键把模型变成手机可扫的网页

双击运行（或命令行运行），它会：
  1. 找本机在局域网里的 IP
  2. 在 8000 端口开一个只对局域网开放的小服务器
  3. 生成二维码，弹出窗口给你扫

手机连同一个 Wi-Fi，扫一下就能看，不需要上传、不需要联网。

停止：按 Ctrl+C，或直接关掉这个黑窗口。
"""

import http.server
import os
import socket
import socketserver
import sys
import threading
import time
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # 最终模型
SRC = os.path.join(ROOT, "03_交互展示", "宿舍交互展示.html")
PUB = os.path.join(HERE, "public")
PAGE = "dorm.html"
PORT = 8000

sys.path.insert(0, HERE)
import qr  # noqa: E402


def all_ips():
    """列出本机所有局域网地址。Windows 热点的 192.168.137.1 永远排第一——
    那个地址是固定的，做二维码最稳。"""
    out = []
    try:
        import re as _re
        import subprocess
        txt = subprocess.check_output(["ipconfig"], creationflags=0x08000000)
        for enc in ("gbk", "utf-8", "latin-1"):
            try:
                txt = txt.decode(enc)
                break
            except Exception:
                continue
        for m in _re.finditer(r"(?:IPv4|IP Address)[^:]*:\s*([\d.]+)", txt):
            ip = m.group(1).strip()
            if ip.startswith("127.") or ip.startswith("169.254.") or ip == "255.255.255.255":
                continue
            if ip not in out:
                out.append(ip)
    except Exception:
        pass

    if not out:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("223.5.5.5", 80))
            out.append(s.getsockname()[0])
        except Exception:
            out.append("127.0.0.1")
        finally:
            s.close()

    out.sort(key=lambda x: (0 if x.startswith("192.168.137.") else 1))
    return out


def free_port(start):
    for p in range(start, start + 40):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as t:
            t.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                t.bind(("0.0.0.0", p))
                return p
            except OSError:
                continue
    raise RuntimeError("no free port")


def build_public():
    os.makedirs(PUB, exist_ok=True)
    if not os.path.exists(SRC):
        raise SystemExit("ERROR: page not found -> " + SRC)
    with open(SRC, "rb") as f:
        data = f.read()
    # 中文文件名在手机上容易出问题，复制成英文名
    with open(os.path.join(PUB, PAGE), "wb") as f:
        f.write(data)
    return len(data)


def _alive(port):
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:%d/__jiezi" % port, timeout=1.2) as r:
            return r.read().strip() == b"ok"
    except Exception:
        return False


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=PUB, **kw)

    def do_GET(self):
        if self.path == "/__jiezi":
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def log_message(self, fmt, *args):
        ip = self.client_address[0]
        print("  PHONE %s  %s" % (ip, fmt % args))


def make_landing(url, qr_png):
    """本地打开的一张说明页，把二维码放得很大"""
    return """<!doctype html><meta charset="utf-8">
<title>手机扫码查看模型</title>
<style>
 body{margin:0;background:#14161A;color:#E8E4DC;font-family:"Microsoft YaHei",sans-serif;
      display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh}
 h1{font-size:22px;font-weight:600;letter-spacing:2px;margin:0 0 6px}
 .sub{color:#8B857C;font-size:13px;margin-bottom:26px}
 .qr{background:#fff;padding:18px;border-radius:14px;box-shadow:0 12px 40px rgba(0,0,0,.5)}
 .qr img{display:block;width:min(46vh,420px);height:auto;image-rendering:pixelated}
 .url{margin-top:22px;font-family:Consolas,monospace;font-size:19px;color:#C9A227;
      background:rgba(201,162,39,.1);border:1px solid rgba(201,162,39,.35);
      padding:10px 20px;border-radius:8px;letter-spacing:.5px}
 .tip{margin-top:26px;color:#5E5952;font-size:12.5px;line-height:2;text-align:center}
 b{color:#C9A227;font-weight:600}
</style>
<h1>扫一下，手机上就能转</h1>
<div class="sub">芥子 · 宿舍桌面数字化底座</div>
<div class="qr"><img src="%s" alt="QR"></div>
<div class="url">%s</div>
<div class="tip">
  手机和这台电脑要连<b>同一个 Wi-Fi</b><br>
  打不开的话，检查 Windows 防火墙有没有拦住 Python<br>
  这个窗口关掉，服务就停了
</div>
""" % ("file:///" + qr_png.replace("\\", "/"), url)


def main():
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    size = build_public()

    # 端口被占：如果占着的是我们自己，直接退出（避免重复启动）
    if _alive(PORT):
        print("already running on port %d - open the QR page instead." % PORT)
        time.sleep(1.5)
        return
    port = PORT
    ips = all_ips()
    ip = ips[0]
    url = "http://%s:%d/%s" % (ip, port, PAGE)

    n, dark = qr.make(url)
    qr_png = os.path.join(PUB, "qr.png")
    qr.to_png(qr_png, n, dark, px=10)

    import shutil
    shutil.copyfile(qr_png, os.path.join(HERE, "二维码.png"))

    landing = os.path.join(HERE, "_扫码.html")
    with open(landing, "w", encoding="utf-8") as f:
        f.write(make_landing(url, qr_png))

    print("=" * 58)
    print("  JIEZI  -  view the model on your phone")
    print("=" * 58)
    print("  page      %.0f KB" % (size / 1024))
    print("  qr        %d x %d  (version %d)" % (n, n, {21: 1, 25: 2, 29: 3}[n]))
    print("  address   %s" % url)
    for extra in ips[1:]:
        print("  backup    http://%s:%d/%s" % (extra, port, PAGE))
    print()
    print("  1. Phone and PC on the SAME Wi-Fi")
    print("  2. Scan the QR shown in the browser window")
    print("  3. If Windows asks about firewall, click Allow")
    print()
    print("  Press Ctrl+C to stop")
    print("=" * 58)

    webbrowser.open("file:///" + landing.replace("\\", "/"))

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("0.0.0.0", port), Handler) as httpd:
        httpd.daemon_threads = True
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  stopped.")


if __name__ == "__main__":
    main()
