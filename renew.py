#!/usr/bin/env python3
import asyncio
import os
import requests
from playwright.async_api import async_playwright

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
        browser = await p.chromium.launch(headless=True)
        # 增加语言和时区，模拟真实浏览器环境
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            locale="zh-CN"
        )
        page = await context.new_page()

        # 监听网络响应以调试 Loading 问题
        async def log_response(response):
            if "auth/login" in response.url:
                resp_text = await response.text()
                print(f"[DEBUG] 登录响应: {response.status} - {resp_text}")
        page.on("response", log_response)

        # 1. 访问登录页
        await page.goto("https://dash.aclclouds.com/auth/login", wait_until="networkidle")
        await page.screenshot(path="step1.png")
        
        # 2. 填充凭证
        await page.locator("#username").fill(EMAIL)
        await page.locator("#password").fill(PASSWORD)
        
        # 3. 触发验证码
        await page.locator('div.auth-captcha-inner[role="checkbox"]').click()
        await asyncio.sleep(2)
        await page.screenshot(path="step2.png")
        send_tg_photo("已勾选验证码", "step2.png")
        
        # 等待验证通过
        await page.wait_for_selector('div.auth-captcha-inner[aria-checked="true"]', timeout=15000)
        
        # 4. 提交表单
        await page.locator('button[type="submit"]').click()
        print("[INFO] 已点击登录，等待响应...")
        
        # 等待页面加载或登录成功跳转
        try:
            await page.wait_for_load_state("networkidle", timeout=20000)
        except:
            print("[WARN] 等待页面加载超时，检查状态...")

        await page.screenshot(path="step3.png")
        send_tg_photo("登录结果截图", "step3.png")
        
        # 5. 执行续期
        if "dashboard" in page.url or "client" in page.url:
            print("[INFO] 登录成功，正在获取项目...")
            projects_resp = await context.request.get("https://dash.aclclouds.com/api/client")
            projects = projects_resp.json().get("data", [])
            for project in projects:
                p_id = project['attributes']['identifier']
                print(f"[INFO] 正在续期项目: {p_id}")
                res = await context.request.post(f"https://dash.aclclouds.com/api/client/servers/{p_id}/upgrade/renew")
                print(f"[INFO] 续期响应: {res.status}")
        else:
            print("[ERROR] 登录失败，请检查 [DEBUG] 日志")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_renew())
