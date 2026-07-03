#!/usr/bin/env python3
import asyncio
import os
import requests
from playwright.async_api import async_playwright

# 环境变量读取
EMAIL = os.environ.get("ACLCLOUDS_EMAIL", "").strip()
PASSWORD = os.environ.get("ACLCLOUDS_PASSWORD", "").strip()
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "").strip()
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "").strip()

def send_tg_photo(caption, photo_path):
    if not TG_BOT_TOKEN or not TG_CHAT_ID or not os.path.exists(photo_path):
        return
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
    try:
        with open(photo_path, 'rb') as f:
            requests.post(url, data={'chat_id': TG_CHAT_ID, 'caption': caption}, files={'photo': f})
    except Exception as e:
        print(f"[ERROR] TG 推送失败: {e}")

async def run_renew():
    async with async_playwright() as p:
        # 1. 启动浏览器并配置强模拟环境
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale="zh-CN"
        )
        page = await context.new_page()

        # 2. 访问并等待页面加载
        print("[INFO] 访问登录页...")
        await page.goto("https://dash.aclclouds.com/auth/login", wait_until="networkidle")
        await page.screenshot(path="step1.png")
        send_tg_photo("已进入登录页", "step1.png")

        # 3. 填充凭证
        print("[INFO] 填充凭证...")
        await page.locator("#username").fill(EMAIL)
        await page.locator("#password").fill(PASSWORD)
        
        # 4. 点击验证码
        print("[INFO] 点击验证码...")
        await page.locator('div.auth-captcha-inner[role="checkbox"]').click()
        
        # 确保验证码状态更新
        await page.wait_for_selector('div.auth-captcha-inner[aria-checked="true"]', timeout=15000)
        await page.screenshot(path="step2.png")
        send_tg_photo("验证码已打勾", "step2.png")

        # 5. 稳健提交：使用回车键触发提交
        print("[INFO] 执行回车键提交...")
        await page.locator("#password").press("Enter")
        
        # 6. 等待跳转 (SPA通常会跳转到 /dashboard)
        try:
            # 等待 URL 包含 dashboard 或 client
            await page.wait_for_url("**/dashboard*", timeout=20000)
            await page.wait_for_load_state("networkidle")
            print("[INFO] ✅ 成功进入 Dashboard")
        except:
            print("[WARN] 页面未检测到跳转，检查登录状态...")

        await page.screenshot(path="step3.png")
        send_tg_photo("最终登录结果", "step3.png")

        # 7. 续期逻辑
        if "dashboard" in page.url or "client" in page.url:
            print("[INFO] 登录成功，准备续期...")
            # 使用登录后的上下文直接调用 API
            projects_resp = await context.request.get("https://dash.aclclouds.com/api/client")
            projects = projects_resp.json().get("data", [])
            for project in projects:
                p_id = project['attributes']['identifier']
                print(f"[INFO] 续期项目: {p_id}")
                res = await context.request.post(f"https://dash.aclclouds.com/api/client/servers/{p_id}/upgrade/renew")
                print(f"[INFO] 续期响应: {res.status}")
        else:
            print("[ERROR] 无法续期，未检测到登录后的页面")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_renew())
