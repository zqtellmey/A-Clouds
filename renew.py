#!/usr/bin/env python3
import os
import sys
import traceback
import requests

COOKIES_STR = os.environ.get("ACL_COOKIES", "").strip()
BASE_URL    = "https://dash.aclclouds.com"
API_BASE    = f"{BASE_URL}/api"

def parse_cookies(cookie_str):
    cookie_dict = {}
    items = cookie_str.split(';')
    for item in items:
        if '=' in item:
            key, val = item.split('=', 1)
            cookie_dict[key.strip()] = val.strip()
    return cookie_dict

class ACLCloudsAPI:
    def __init__(self, cookies_dict):
        self.session = requests.Session()
        # 将原始 Cookie 存入 Session
        self.session.cookies.set("aclclouds_session", cookies_dict.get("aclclouds_session"), domain="dash.aclclouds.com")
        self.session.cookies.set("XSRF-TOKEN", cookies_dict.get("XSRF-TOKEN"), domain="dash.aclclouds.com")
        
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{BASE_URL}/",
            "Origin": BASE_URL,
        })

    def _update_headers(self):
        # 每次请求前，强制从 Session Cookie 中读取最新的 XSRF-TOKEN
        xsrf = self.session.cookies.get("XSRF-TOKEN")
        if xsrf:
            self.session.headers["X-XSRF-TOKEN"] = xsrf

    def get_projects(self):
        self._update_headers()
        r = self.session.get(f"{BASE_URL}/api/client", timeout=20)
        if r.status_code != 200:
            raise RuntimeError(f"获取项目失败: {r.status_code}")
        return [item.get("attributes") for item in r.json().get("data", []) if item.get("attributes")]

    def renew_project(self, project):
        self._update_headers() # 核心：续期前必须同步 Header
        identifier = project.get("identifier")
        url = f"{API_BASE}/client/servers/{identifier}/upgrade/renew"
        
        # 强制添加必要的 CSRF 头部
        headers = {"X-XSRF-TOKEN": self.session.cookies.get("XSRF-TOKEN")}
        r = self.session.post(url, headers=headers, timeout=20)
        
        if r.status_code == 200:
            return True
        else:
            raise RuntimeError(f"续期失败 (HTTP {r.status_code}): {r.text}")

def run():
    if not COOKIES_STR:
        raise RuntimeError("请在 Secrets 中配置 ACL_COOKIES")
    
    api = ACLCloudsAPI(parse_cookies(COOKIES_STR))
    projects = api.get_projects()
    for project in projects:
        name = project.get("name", "未知项目")
        print(f"[INFO] 正在续期项目: {name} ...", flush=True)
        try:
            api.renew_project(project)
            print(f"[INFO] ✅ {name} 续期成功", flush=True)
        except Exception as e:
            print(f"[ERROR] 续期 {name} 失败: {e}", flush=True)

if __name__ == "__main__":
    try:
        run()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
