#!/usr/bin/env python3
import os
import sys
import traceback
import requests
import random
import time

COOKIES_STR = os.environ.get("ACL_COOKIES", "").strip()
BASE_URL    = "https://dash.aclclouds.com"

def parse_cookies(cookie_str):
    cookie_dict = {}
    for item in cookie_str.split(';'):
        if '=' in item:
            key, val = item.split('=', 1)
            cookie_dict[key.strip()] = val.strip()
    return cookie_dict

class ACLCloudsAPI:
    def __init__(self, cookies_dict):
        self.session = requests.Session()
        # 初始化 Session
        self.session.cookies.set("aclclouds_session", cookies_dict.get("aclclouds_session"), domain="dash.aclclouds.com")
        self.session.cookies.set("XSRF-TOKEN", cookies_dict.get("XSRF-TOKEN"), domain="dash.aclclouds.com")
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Referer": f"{BASE_URL}/",
            "Origin": BASE_URL,
        })

    def _get_captcha_token(self):
        """步骤1：先调用验证码接口获取 token"""
        # 同步当前的 CSRF
        self.session.headers["X-XSRF-TOKEN"] = self.session.cookies.get("XSRF-TOKEN")
        
        # 模拟真实行为载荷
        payload = {
            "mouse_movements": random.randint(300, 400),
            "mouse_distance": random.randint(5000, 6000),
            "clicks": 1,
            "key_presses": random.randint(2, 5),
            "elapsed_ms": random.randint(3000, 6000),
        }
        
        r = self.session.post(f"{BASE_URL}/auth/captcha", json=payload, timeout=20)
        if r.status_code == 200:
            return r.json().get("token")
        return None

    def renew_project(self, project):
        """步骤2：带着 token 发起续期请求"""
        captcha_token = self._get_captcha_token()
        if not captcha_token:
            raise RuntimeError("无法获取 Captcha Token")

        identifier = project.get("identifier")
        url = f"{BASE_URL}/api/client/servers/{identifier}/upgrade/renew"
        
        # 核心：将 token 放入载荷中
        data = {"captcha_token": captcha_token}
        
        # 确保 Header 同步
        self.session.headers["X-XSRF-TOKEN"] = self.session.cookies.get("XSRF-TOKEN")
        
        r = self.session.post(url, json=data, timeout=20)
        if r.status_code == 200:
            return True
        else:
            raise RuntimeError(f"续期失败 (HTTP {r.status_code}): {r.text}")

    def get_projects(self):
        r = self.session.get(f"{BASE_URL}/api/client", timeout=20)
        return [item.get("attributes") for item in r.json().get("data", []) if item.get("attributes")]

def run():
    if not COOKIES_STR: raise RuntimeError("请在 Secrets 中配置 ACL_COOKIES")
    api = ACLCloudsAPI(parse_cookies(COOKIES_STR))
    
    for project in api.get_projects():
        name = project.get("name", "未知项目")
        print(f"[INFO] 正在续期: {name} ...", flush=True)
        api.renew_project(project)
        print(f"[INFO] ✅ {name} 续期成功", flush=True)

if __name__ == "__main__":
    try:
        run()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
