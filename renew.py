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

async def run_renew():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale="zh-CN"
        )
        page = await context.new_page()

        # --- 焊死登录部分 (一个字没动) ---
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

        # --- 获取 API 数据并推送剩余时间 ---
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
                
                # 推送信息
                status_text = "⚠️ 需立即续期" if hours_left < 2 else "ℹ️ 时间充足"
                report = f"服务器: {s_name}\n剩余时间: {hours_left:.2f} 小时\n状态: {status_text}"
                send_tg_msg(report)
                
                # --- 操作阶段：精确处理弹窗验证 ---
                renew_btn = page.locator('button.client-btn--secondary:has-text("Renew")')
                if await renew_btn.count() > 0:
                    print(f"[LOG] 找到服务器 {s_name} 的 Renew 按钮，准备点击")
                    await renew_btn.scroll_into_view_if_needed()
                    await renew_btn.evaluate("el => el.click()")
                    
                    # 使用更精确的选择器，专门针对置顶 Dialog 里的 checkbox
                    captcha_locator = page.locator('div[role="dialog"] .auth-captcha-inner[role="checkbox"]')
                    await captcha_locator.wait_for(state="visible", timeout=10000)
                    await captcha_locator.click()
                    
                    # 等待该 checkbox 状态变更为 checked
                    await captcha_locator.wait_for(state="attached")
                    # 直接监听属性变化，确保点击成功
                    await page.wait_for_selector('div[role="dialog"] .auth-captcha-inner[aria-checked="true"]', timeout=15000)
                    
                    await page.screenshot(path="renew_success.png")
                    send_tg_photo(f"已完成 {s_name} 的 Renew 操作", "renew_success.png")
                else:
                    print(f"[LOG] 未能找到服务器 {s_name} 的 Renew 按钮")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_renew())
