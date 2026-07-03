#!/usr/bin/env python3
import os
import sys
import traceback
import requests

# ── 环境变量 ──
# 格式: aclclouds_session=xxx; XSRF-TOKEN=yyy
COOKIES_STR = os.environ.get("ACL_COOKIES", "").strip()

BASE_URL  = "https://dash.aclclouds.com"
API_BASE  = f"{BASE_URL}/api"

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
        session_val = cookies_dict.get("aclclouds_session")
        xsrf_val = cookies_dict.get("XSRF-TOKEN")
        
        if not session_val or not xsrf_val:
            raise RuntimeError("Cookie 中缺少 aclclouds_session 或 XSRF-TOKEN")

        self.session.cookies.set("aclclouds_session", session_val, domain="dash.aclclouds.com")
        self.session.cookies.set("XSRF-TOKEN", xsrf_val, domain="dash.aclclouds.com")
        
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            "X-XSRF-TOKEN": xsrf_val,
            "Accept": "application/json, text/plain, */*",
        })

    def get_projects(self):
        url = f"{BASE_URL}/api/client"
        r = self.session.get(url, timeout=20)
        if r.status_code != 200:
            raise RuntimeError(f"获取项目列表失败 (HTTP {r.status_code})")
        return [item.get("attributes") for item in r.json().get("data", []) if item.get("attributes")]

    def renew_project(self, project):
        identifier = project.get("identifier")
        url = f"{API_BASE}/client/servers/{identifier}/upgrade/renew"
        r = self.session.post(url, timeout=20)
        if r.status_code == 200:
            return True
        raise RuntimeError(f"续期失败: {r.text}")

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
        print("[INFO] 脚本执行完毕", flush=True)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
