#!/usr/bin/env python3
import os
import sys
import subprocess

def install_requirements():
    try:
        import requests
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])

install_requirements()

import requests
import json
import random
import traceback

# 环境变量
EMAIL             = os.environ.get("ACLCLOUDS_EMAIL", "").strip()
PASSWORD          = os.environ.get("ACLCLOUDS_PASSWORD", "").strip()
BASE_URL          = "https://dash.aclclouds.com"
LOGIN_URL         = f"{BASE_URL}/auth/login"
CAPTCHA_URL       = f"{BASE_URL}/auth/captcha"

class ACLCloudsAPI:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": LOGIN_URL,
            "Origin": BASE_URL
        })

    def _get_captcha_token(self):
        # 核心逻辑：强制访问首页并立即提取 XSRF-TOKEN
        log("访问登录页并抓取最新 CSRF Token...")
        resp = self.session.get(LOGIN_URL, timeout=20)
        
        # Laravel 框架会自动设置 XSRF-TOKEN cookie
        xsrf = self.session.cookies.get("XSRF-TOKEN")
        if not xsrf:
            log_error("未能在响应中找到 XSRF-TOKEN")
            return None
        
        # 必须设置此 Header，否则 Laravel 会报 419
        self.session.headers["X-XSRF-TOKEN"] = xsrf
        
        fake_behavior = {
            "mouse_movements": random.randint(300, 400),
            "mouse_distance": random.randint(5000, 6000),
            "clicks": 1,
            "key_presses": random.randint(2, 5),
            "elapsed_ms": random.randint(3000, 6000),
        }
        
        log("提交行为数据...")
        cr = self.session.post(CAPTCHA_URL, json=fake_behavior, timeout=20)
        
        if cr.status_code == 200:
            return cr.json().get("token")
        else:
            log_error(f"Captcha 失败 ({cr.status_code}): {cr.text}")
            return None

    def login(self, email, password):
        # 重新获取 token 和最新的 csrf
        token = self._get_captcha_token()
        if not token:
            raise RuntimeError("验证码令牌获取失败")
            
        payload = {
            "user": email,
            "password": password,
            "captcha_answer": "human",
            "captcha_token": token,
        }
        
        log("发送登录请求...")
        r = self.session.post(LOGIN_URL, json=payload, timeout=20)
        if r.status_code == 200:
            log("登录成功！")
            return True
        else:
            raise RuntimeError(f"登录失败 ({r.status_code}): {r.text}")

def log(msg): print(f"[INFO] {msg}", flush=True)
def log_error(msg): print(f"[ERROR] {msg}", flush=True)

def run():
    api = ACLCloudsAPI()
    api.login(EMAIL, PASSWORD)
    log("脚本执行完毕")

if __name__ == "__main__":
    try:
        run()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
