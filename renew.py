#!/usr/bin/env python3
"""
ACLClouds 自动续期脚本 (纯 API 版)
"""

import os
import re
import sys
import json
import time
import traceback
from urllib.request import Request, urlopen

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# ── 环境变量 ─────────────────────────────────────────────
EMAIL             = os.environ.get("ACLCLOUDS_EMAIL", "").strip()
PASSWORD          = os.environ.get("ACLCLOUDS_PASSWORD", "").strip()
TG_BOT_TOKEN      = os.environ.get("TG_BOT_TOKEN", "").strip()
TG_CHAT_ID        = os.environ.get("TG_CHAT_ID", "").strip()
WXPUSHER_APPTOKEN = os.environ.get("WXPUSHER_APPTOKEN", "").strip()
WXPUSHER_UID      = os.environ.get("WXPUSHER_UID", "").strip()

RENEW_THRESHOLD_DAYS = 0.08
BASE_URL  = "https://dash.aclclouds.com"
LOGIN_URL = f"{BASE_URL}/auth/login"
API_BASE  = f"{BASE_URL}/api"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Origin": BASE_URL,
    "Referer": LOGIN_URL,
    "x-requested-with": "XMLHttpRequest",
}

def log(msg):       print(f"[INFO] {msg}", flush=True)
def log_warn(msg):  print(f"[WARN] {msg}", flush=True)
def log_error(msg): print(f"[ERROR] {msg}", flush=True)

# ── 推送函数 ──────────────────────────────────────────────
def send_all_push(text: str):
    # 简化版推送逻辑，保持代码整洁
    log(f"推送内容: {text[:50]}...")

# ── 解析剩余时间 ──────────────────────────────────────────
def parse_expires(text):
    if text is None: return None
    s = str(text).strip()
    try: return float(s) / 86400
    except: pass
    return None

# ── API 封装 ──────────────────────────────────────────────
class ACLCloudsAPI:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _set_xsrf(self):
        from urllib.parse import unquote
        xsrf = self.session.cookies.get("XSRF-TOKEN", "")
        if xsrf:
            self.session.headers["x-xsrf-token"] = unquote(xsrf)

    def _get_captcha_token(self):
        log("GET 登录页，获取初始 Cookie ...")
        self.session.get(LOGIN_URL, timeout=20)
        self._set_xsrf()

        captcha_url = f"{BASE_URL}/auth/captcha"
        fake_behavior = {
            "mouse_movements": 320,
            "mouse_distance": 5800,
            "clicks": 1,
            "key_presses": 3,
            "elapsed_ms": 45000,
        }
        
        log(f"POST {captcha_url} ...")
        cr = self.session.post(captcha_url, json=fake_behavior, timeout=20)
        
        if cr.status_code == 200:
            data = cr.json()
            if data.get("passed"):
                token = data.get("token")
                log("captcha 验证通过")
                return token
            else:
                log_error(f"Captcha 响应未通过: {data}")
        else:
            log_error(f"Captcha 接口报错 (HTTP {cr.status_code}): {cr.text}")
        return None

    def login(self, email, password):
        captcha_token = self._get_captcha_token()
        if not captcha_token:
            raise RuntimeError("无法获取有效的验证码 Token")
            
        payload = {
            "user": email,
            "password": password,
            "captcha_answer": "human",
            "captcha_token": captcha_token,
        }
        
        log("开始发送登录请求...")
        r = self.session.post(LOGIN_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=20)
        log(f"登录响应: HTTP {r.status_code}")
        
        if r.status_code == 200:
            log("登录成功 ✅")
            return True
        else:
            log_error(f"登录失败，服务器响应: {r.text}")
            raise RuntimeError(f"登录失败，状态码: {r.status_code}")

    def get_projects(self):
        url = f"{BASE_URL}/api/client"
        r = self.session.get(url, timeout=20)
        if r.status_code != 200: raise RuntimeError(f"获取列表失败: {r.status_code}")
        return [item.get("attributes") for item in r.json().get("data", []) if item.get("attributes")]

    def renew_project(self, project):
        identifier = project.get("identifier")
        url = f"{API_BASE}/client/servers/{identifier}/upgrade/renew"
        r = self.session.post(url, timeout=20)
        if r.status_code == 200:
            return True
        raise RuntimeError(f"续期失败: {r.text}")

# ── 主流程 ────────────────────────────────────────────────
def run():
    if not EMAIL or not PASSWORD: raise RuntimeError("缺少环境变量")
    api = ACLCloudsAPI()
    api.login(EMAIL, PASSWORD)
    
    projects = api.get_projects()
    for project in projects:
        name = project.get("name", "未知项目")
        remaining = parse_expires(project.get("expires_at"))
        if remaining is not None and remaining < RENEW_THRESHOLD_DAYS:
            log(f"[{name}] 开始续期...")
            api.renew_project(project)
            log(f"[{name}] ✅ 续期成功")

if __name__ == "__main__":
    try:
        run()
        log("脚本执行完毕")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
