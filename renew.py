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
    with open(photo_path, 'rb') as f:
        requests.post(url, data={'chat_id': TG_CHAT_ID, 'caption': caption}, files={'photo': f})

async def run_renew():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
        page = await context.new_page()

        # 1. 访问登录页
        await page.goto("https://dash.aclclouds.com/auth/login", wait_until="networkidle")
        await page.screenshot(path="step1.png")
        send_tg_photo("已进入登录页", "step1.png")

        # 2. 填充并点击
        await page.locator("#username").fill(EMAIL)
        await page.locator("#password").fill(PASSWORD)
        await page.locator('div.auth-captcha-inner[role="checkbox"]').click()
        
        # 3. 等待通过并截图
        await asyncio.sleep(3) # 缓冲
        await page.screenshot(path="step2.png")
        send_tg_photo("点击验证码后", "step2.png")
        
        await page.wait_for_selector('div.auth-captcha-inner[aria-checked="true"]', timeout=10000)
        
        # 4. 提交
        await page.locator('button[type="submit"]').click()
        await page.wait_for_load_state("networkidle")
        
        # 5. 最终结果
        await page.screenshot(path="step3.png")
        send_tg_photo("登录结果截图", "step3.png")
        
        if "dashboard" in page.url or "client" in page.url:
            print("[INFO] 登录成功")
            # 此处执行续期...
        else:
            print("[ERROR] 登录页面未跳转")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_renew())
