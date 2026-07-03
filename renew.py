#!/usr/bin/env python3
import asyncio
import os
import requests
from playwright.async_api import async_playwright

# 环境变量
EMAIL = os.environ.get("ACLCLOUDS_EMAIL", "").strip()
PASSWORD = os.environ.get("ACLCLOUDS_PASSWORD", "").strip()
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "").strip()
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "").strip()

def send_tg_photo(caption, photo_path):
    """使用 requests 发送图片到 Telegram"""
    if not TG_BOT_TOKEN or not TG_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
    with open(photo_path, 'rb') as f:
        files = {'photo': f}
        data = {'chat_id': TG_CHAT_ID, 'caption': caption}
        requests.post(url, data=data, files=files)

async def run_debug():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
        page = await context.new_page()

        # 1. 访问并截图
        await page.goto("https://dash.aclclouds.com/auth/login")
        await page.screenshot(path="step1_login_page.png")
        send_tg_photo("进入登录页", "step1_login_page.png")

        # 2. 填写信息
        await page.fill('input[type="email"]', EMAIL)
        await page.fill('input[type="password"]', PASSWORD)

        # 3. 点击验证码并截图确认
        captcha = page.locator('div.auth-captcha-inner[role="checkbox"]')
        await captcha.click()
        await asyncio.sleep(2)
        await page.screenshot(path="step2_after_captcha.png")
        send_tg_photo("点击验证码后截图", "step2_after_captcha.png")

        # 4. 提交登录截图
        await page.click('button[type="submit"]')
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        await page.screenshot(path="step3_after_login.png")
        send_tg_photo("登录尝试结果", "step3_after_login.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_debug())
