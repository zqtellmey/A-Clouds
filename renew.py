#!/usr/bin/env python3
import asyncio
import os
import requests
from datetime import datetime, timezone
from playwright.async_api import async_playwright

# 环境变量
EMAIL = os.environ.get("ACLCLOUDS_EMAIL", "").strip()
PASSWORD = os.environ.get("ACLCLOUDS_PASSWORD", "").strip()
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "").strip()
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "").strip()

def send_tg_msg(text):
    if TG_BOT_TOKEN and TG_CHAT_ID:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML"})

def parse_remaining_days(expires_str):
    try:
        dt = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
        remaining = (dt - datetime.now(timezone.utc)).total_seconds() / 86400
        return remaining
    except:
        return 999 

async def handle_captcha(page):
    captcha = page.locator('div.auth-captcha-inner[role="checkbox"]')
    await captcha.wait_for(state="visible", timeout=10000)
    await captcha.click()
    await page.wait_for_selector('div.auth-captcha-inner[aria-checked="true"]', timeout=15000)

async def run_renew():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
        page = await context.new_page()

        # --- 以下为焊死的登录部分 ---
        await page.goto("https://dash.aclclouds.com/auth/login", wait_until="networkidle")
        await page.locator("#username").fill(EMAIL)
        await page.locator("#password").fill(PASSWORD)
        await handle_captcha(page)
        await page.locator("#password").press("Enter")
        await page.wait_for_load_state("networkidle")
        # --- 登录结束 ---

        # 1. 获取服务器状态
        status_resp = await context.request.get("https://dash.aclclouds.com/api/client")
        servers = status_resp.json().get("data", [])
        
        # 2. 进入项目操作页
        await page.goto("https://dash.aclclouds.com/projects", wait_until="networkidle")
        
        for server in servers:
            attrs = server['attributes']
            s_name = attrs['name']
            remaining = parse_remaining_days(attrs['expires_at'])
            
            report = f"<b>服务器: {s_name}</b>\n剩余时间: {remaining:.2f} 天"
            
            # 判断逻辑：小于 0.0833 天（2小时）进行操作
            if remaining < 0.0833:
                # 使用鲁棒性强的定位器
                reactivate_btn = page.locator('button:has-text("Reactivate")')
                renew_btn = page.locator('button:has-text("Renew")')
                
                if await reactivate_btn.count() > 0:
                    await reactivate_btn.click()
                    await handle_captcha(page)
                    report += "\n状态: ✅ <b>已执行 Reactivate</b>"
                elif await renew_btn.count() > 0:
                    await renew_btn.click()
                    await handle_captcha(page)
                    report += "\n状态: ✅ <b>已执行 Renew</b>"
                else:
                    report += "\n状态: ⚠️ 按钮未找到"
            else:
                report += "\n状态: ℹ️ 无需操作"
            
            send_tg_msg(report)
        
        await page.screenshot(path="final.png")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_renew())
