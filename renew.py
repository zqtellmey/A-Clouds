#!/usr/bin/env python3
import os
import sys
import traceback
import requests
import json

# 环境变量
COOKIES_STR = os.environ.get("ACL_COOKIES", "").strip()
# 将你抓包到的 JSON 完整载荷放进这个环境变量
GATE_PAYLOAD = os.environ.get("ACL_GATE_PAYLOAD", "{}").strip()
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
        self.session.cookies.set("aclclouds_session", cookies_dict.get("aclclouds_session"), domain="dash.aclclouds.com")
        self.session.cookies.set("XSRF-TOKEN", cookies_dict.get("XSRF-TOKEN"), domain="dash.aclclouds.com")
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "X-XSRF-TOKEN": cookies_dict.get("XSRF-TOKEN")
        })

    def renew_project(self, project):
        identifier = project.get("identifier")
        url = f"{BASE_URL}/api/client/servers/{identifier}/upgrade/renew"
        
        # 直接使用抓包得到的载荷
        payload = json.loads(GATE_PAYLOAD)
        
        print(f"[INFO] 正在提交续期请求...", flush=True)
        r = self.session.post(url, json=payload, timeout=20)
        
        if r.status_code == 200:
            return True
        else:
            raise RuntimeError(f"续期失败 (HTTP {r.status_code}): {r.text}")

    def get_projects(self):
        r = self.session.get(f"{BASE_URL}/api/client", timeout=20)
        return [item.get("attributes") for item in r.json().get("data", []) if item.get("attributes")]

def run():
    if not COOKIES_STR or not GATE_PAYLOAD:
        raise RuntimeError("请在 Secrets 中配置 ACL_COOKIES 和 ACL_GATE_PAYLOAD")
    
    api = ACLCloudsAPI(parse_cookies(COOKIES_STR))
    for project in api.get_projects():
        print(f"[INFO] 正在续期: {project.get('name')} ...", flush=True)
        api.renew_project(project)
        print(f"[INFO] ✅ 成功", flush=True)

if __name__ == "__main__":
    try: run()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
