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
            final_caption = f"ACLClouds: {caption}"
            requests.post(url, data={'chat_id': TG_CHAT_ID, 'caption': final_caption}, files={'photo': f})
    except Exception as e:
        print(f"[ERROR] TG 推送失败: {e}")

def send_tg_msg(text):
    if TG_BOT_TOKEN and TG_CHAT_ID:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        final_text = f"<b>ACLClouds</b>\n{text}"
        requests.post(url, json={"chat_id": TG_CHAT_ID, "text": final_text, "parse_mode": "HTML"})

async def handle_captcha(page):
    captcha = page.locator('div.auth-captcha-inner[role="checkbox"]')
    if await captcha.count() > 0:
        await captcha.click()
        # 宽容等待，不强制要求必须看到 aria-checked 以防止 Renew 时超时
        try:
            await page.wait_for_selector('div.auth-captcha-inner[aria-checked="true"]', timeout=5000)
        except:
            print("[INFO] 验证码状态未改变，继续执行...")

async def run_renew():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale="zh-CN"
        )
        page = await context.new_page()

        # --- 焊死登录部分 (完全恢复你确认过的逻辑) ---
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
            await page.wait_for_url("**/dashboard*", timeout=20000)
            await page.wait_for_load_state("networkidle")
        except:
            pass

        await page.screenshot(path="step3.png")
        send_tg_photo("最终登录结果", "step3.png")
        # --- 登录部分结束 ---

        # --- 焊死获取数据并推送的功能 ---
        print("[INFO] 开始获取服务器信息...")
        resp = await context.request.get("https://dash.aclclouds.com/api/client")
        if resp.ok:
            data = await resp.json()
            servers = data.get("data", [])
            await page.goto("https://dash.aclclouds.com/projects", wait_until="networkidle")
            
            now = datetime.now(timezone.utc)
            for server in servers:
                attrs = server['attributes']
                s_name = attrs['name']
                expires_at = datetime.fromisoformat(attrs['expires_at'])
                hours_left = (expires_at - now).total_seconds() / 3600
                
                # 汇报逻辑（焊死）
                status_text = "⚠️ 需立即续期" if hours_left < 2 else "ℹ️ 时间充足"
                report = f"服务器: {s_name}\n剩余时间: {hours_left:.2f} 小时\n状态: {status_text}"
                send_tg_msg(report)
                
                # 动作逻辑（追加）
                # 1. 优先 Reactivate
                reactivate_btn = page.locator('button:has-text("Reactivate")')
                if await reactivate_btn.count() > 0:
                    await reactivate_btn.click()
                    await handle_captcha(page)
                    send_tg_msg(f"服务器: {s_name}\n状态: ✅ 已执行 Reactivate")
                    continue
                
                # 2. Renew
                if hours_left < 2:
                    renew_btn = page.locator('button.client-btn--secondary:has-text("Renew")')
                    if await renew_btn.count() > 0:
                        await renew_btn.click()
                        await handle_captcha(page)
                        send_tg_msg(f"服务器: {s_name}\n状态: ✅ 已执行 Renew")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_renew())
