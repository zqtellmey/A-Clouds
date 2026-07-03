#!/usr/bin/env python3
import os
import sys
import traceback
import requests

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
        # 存入 Session
        self.session.cookies.set("aclclouds_session", cookies_dict.get("aclclouds_session"), domain="dash.aclclouds.com")
        self.session.cookies.set("XSRF-TOKEN", cookies_dict.get("XSRF-TOKEN"), domain="dash.aclclouds.com")
        
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Referer": f"{BASE_URL}/",
            "Origin": BASE_URL,
        })

    def _sync_and_get_token(self):
        """核心修复：在执行 POST 前强制刷新 CSRF Cookie 同步"""
        # 1. 访问首页，强制触发服务器更新 XSRF-TOKEN
        resp = self.session.get(BASE_URL, timeout=15)
        # 2. 从响应的 Cookie 中提取最新的 XSRF-TOKEN
        xsrf = self.session.cookies.get("XSRF-TOKEN")
        if xsrf:
            self.session.headers["X-XSRF-TOKEN"] = xsrf
        return xsrf

    def get_projects(self):
        r = self.session.get(f"{BASE_URL}/api/client", timeout=20)
        if r.status_code != 200:
            raise RuntimeError(f"获取项目列表失败: {r.status_code}")
        return [item.get("attributes") for item in r.json().get("data", []) if item.get("attributes")]

    def renew_project(self, project):
        # 执行续期前强制同步
        self._sync_and_get_token()
        
        identifier = project.get("identifier")
        url = f"{BASE_URL}/api/client/servers/{identifier}/upgrade/renew"
        
        r = self.session.post(url, timeout=20)
        
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
        api.renew_project(project)
        print(f"[INFO] ✅ {name} 续期成功", flush=True)

if __name__ == "__main__":
    try:
        run()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
