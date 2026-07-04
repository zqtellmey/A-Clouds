#!/usr/bin/env python3
import asyncio
import os
import requests
from datetime import datetime, timezone
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
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080),
            locale="zh-CN"
        )
        page = await context.new_page()

        # --- 焊死登录部分 (一个字都没改，确保逻辑完全一致) ---
        print("[INFO] 访问登录页...")
        await page.goto("https://dash.aclclouds.com/auth/login", wait_until="networkidle")
        await page.screenshot(path="step1.png")
        send_tg_photo("已进入登录页", "step1.png")

        print("[INFO] 填充凭证...")
        await page.locator("#username").fill(EMAIL)
        await page.locator("#password").fill(PASSWORD)
        
        print("[INFO] 点击验证码...")
        await page.locator('div.auth-captcha-inner[role="checkbox"]').click()
        await page.wait_for_selector('div.auth-captcha-inner[aria-checked="true"]', timeout=15000)
        await page.screenshot(path="step2.png")
        send_tg_photo("验证码已打勾", "step2.png")

        print("[INFO] 执行回车键提交...")
        await page.locator("#password").press("Enter")
        
        try:
            # 增加一点点等待时间确保跳转完成
            await page.wait_for_load_state("networkidle", timeout=20000)
            print("[INFO] ✅ 成功进入页面")
        except:
            print("[WARN] 页面加载超时")

        await page.screenshot(path="step3.png")
        send_tg_photo("最终登录结果", "step3.png")
        # --- 登录部分结束 ---

        # --- 获取 API 数据 (修正了之前的 await 错误) ---
        print("[INFO] 开始获取服务器信息...")
        # 这里使用 Playwright 的 request 获取，它会自动带上登录后的 Cookie
        resp = await context.request.get("https://dash.aclclouds.com/api/client")
        
        if resp.ok:
            data = await resp.json()  # <--- 正确补上了 await
            servers = data.get("data", [])
            for server in servers:
                attrs = server['attributes']
                print(f"[LOG] 服务器: {attrs['name']} | 到期时间: {attrs['expires_at']}")
        else:
            print(f"[ERROR] API 返回状态码: {resp.status}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_renew())
