#!/usr/bin/env python3
"""
ACLClouds 自动续期脚本 (完整修正版)
"""

import os
import sys
import subprocess

# 强制确保 requests 已安装
def install_requirements():
    try:
        import requests
    except ImportError:
        print("[INFO] 检测到缺少 requests 库，正在安装...", flush=True)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        print("[INFO] requests 安装完成，继续运行脚本...", flush=True)

install_requirements()

# 此时 requests 已经确保安装，可以正常导入
import requests
import json
import time
import random
import traceback

# ... (后续代码保持不变)

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
    "sec-ch-ua": '"Google Chrome";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
    "sec-ch-ua-platform": '"Windows"',
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Origin": BASE_URL,
    "Referer": LOGIN_URL,
    "x-requested-with": "XMLHttpRequest",
}

def log(msg):       print(f"[INFO] {msg}", flush=True)
def log_warn(msg):  print(f"[WARN] {msg}", flush=True)
def log_error(msg): print(f"[ERROR] {msg}", flush=True)

class ACLCloudsAPI:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _sync_csrf(self):
        # 强制从 Session 中同步 XSRF-TOKEN 到 Header
        cookies = self.session.cookies.get_dict()
        xsrf = cookies.get("XSRF-TOKEN")
        if xsrf:
            self.session.headers["X-XSRF-TOKEN"] = xsrf
            self.session.headers["X-CSRF-TOKEN"] = xsrf

    def _get_captcha_token(self):
        log("1. 获取登录页以初始化 Session...")
        self.session.get(LOGIN_URL, timeout=20)
        self._sync_csrf()

        captcha_url = f"{BASE_URL}/auth/captcha"
        fake_behavior = {
            "mouse_movements": random.randint(300, 400),
            "mouse_distance": random.randint(5000, 6000),
            "clicks": 1,
            "key_presses": random.randint(2, 5),
            "elapsed_ms": random.randint(3000, 6000),
        }
        
        log("2. 提交行为数据获取 Token...")
        cr = self.session.post(captcha_url, json=fake_behavior, timeout=20)
        
        if cr.status_code == 419:
            log_error("CRITICAL: CSRF token mismatch (419). 请检查 Session 是否被阻断。")
            return None
        
        if cr.status_code == 200:
            data = cr.json()
            if data.get("passed"):
                log("验证码已通过")
                return data.get("token")
            log_error(f"验证码拒绝: {data.get('reason')}")
        else:
            log_error(f"Captcha 响应异常 ({cr.status_code}): {cr.text}")
        return None

    def login(self, email, password):
        # 在登录前确保 CSRF 头是最新的
        self._sync_csrf()
        captcha_token = self._get_captcha_token()
        if not captcha_token:
            raise RuntimeError("无法获取有效的验证码 Token")
            
        payload = {
            "user": email,
            "password": password,
            "captcha_answer": "human",
            "captcha_token": captcha_token,
        }
        
        log("3. 发送登录请求...")
        r = self.session.post(LOGIN_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=20)
        
        if r.status_code == 200:
            log("登录成功 ✅")
            return True
        else:
            log_error(f"登录响应异常 ({r.status_code}): {r.text}")
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

def run():
    if not EMAIL or not PASSWORD: raise RuntimeError("缺少环境变量")
    api = ACLCloudsAPI()
    api.login(EMAIL, PASSWORD)
    
    projects = api.get_projects()
    for project in projects:
        name = project.get("name", "未知项目")
        # 简化版时间解析
        expires = project.get("expires_at")
        log(f"项目 {name} 过期时间: {expires}")
        # 如果逻辑需要，在这里添加你的续期阈值判断
        api.renew_project(project)
        log(f"[{name}] ✅ 续期成功")

if __name__ == "__main__":
    try:
        run()
        log("脚本执行完毕")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
