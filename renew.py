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
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/149.0.0.0",
            viewport={'width': 1920, 'height': 1080},
            locale="zh-CN"
        )
        page = await context.new_page()

        # --- 焊死登录部分 ---
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

        # 1. 进入项目页
        await page.goto("https://dash.aclclouds.com/projects", wait_until="networkidle")
        
        # 2. 优先处理 Reactivate
        reactivate_btns = page.locator('button:has-text("Reactivate")')
        count = await reactivate_btns.count()
        if count > 0:
            print(f"[INFO] 发现 {count} 个 Reactivate 按钮，优先执行...")
            for i in range(count):
                await reactivate_btns.nth(i).click()
                await asyncio.sleep(2)
                checkbox = page.locator('div[role="checkbox"]:has-text("I am not a robot")')
                if await checkbox.count() > 0: await checkbox.click()
                await asyncio.sleep(2)
                await page.screenshot(path=f"reactivate_{i}.png")
                send_tg_photo(f"已执行 Reactivate 动作 {i+1}", f"reactivate_{i}.png")
                await asyncio.sleep(2)

        # 3. 获取 API 查询剩余时间
        print("[INFO] 开始获取服务器信息...")
        resp = await context.request.get("https://dash.aclclouds.com/api/client")
        if resp.ok:
            data = await resp.json()
            servers = data.get("data", [])
            now = datetime.now(timezone.utc)
            
            for server in servers:
                attrs = server['attributes']
                s_name = attrs['name']
                expires_at = datetime.fromisoformat(attrs['expires_at'])
                hours_left = (expires_at - now).total_seconds() / 3600
                
                # 若小于2小时，则寻找并 Renew
                if hours_left < 2:
                    renew_btn = page.locator('button.client-btn--secondary:has-text("Renew")').first
                    if await renew_btn.count() > 0:
                        await renew_btn.scroll_into_view_if_needed()
                        await renew_btn.evaluate("el => el.click()")
                        await asyncio.sleep(2)
                        # 处理人机验证
                        checkbox = page.locator('div[role="checkbox"]:has-text("I am not a robot")')
                        if await checkbox.count() > 0: await checkbox.click()
                        await asyncio.sleep(1)
                        target_btn = page.locator('div[role="dialog"] button:has-text("Serveur")')
                        if await target_btn.count() > 0: await target_btn.click()
                        
                        await asyncio.sleep(2)
                        await page.screenshot(path="renew_final_result.png")
                        send_tg_photo(f"已尝试完成 {s_name} 的 Renew 交互式验证", "renew_final_result.png")
                        
                        # 续期后再次查询 API
                        await asyncio.sleep(5)
                        new_resp = await context.request.get("https://dash.aclclouds.com/api/client")
                        if new_resp.ok:
                            new_data = await new_resp.json()
                            for n_s in new_data.get("data", []):
                                if n_s['attributes']['name'] == s_name:
                                    n_h = (datetime.fromisoformat(n_s['attributes']['expires_at']) - now).total_seconds() / 3600
                                    send_tg_msg(f"服务器: {s_name}\n状态: ✅ 续期后剩余时间: {n_h:.2f} 小时")
                    else:
                        print(f"[LOG] 需续期但未找到 Renew 按钮")
                        await page.screenshot(path="not_found.png")
                        send_tg_photo(f"服务器 {s_name} 剩余 {hours_left:.2f} 小时，但未找到 Renew 按钮！", "not_found.png")
                else:
                    send_tg_msg(f"服务器: {s_name}\n剩余时间: {hours_left:.2f} 小时\n状态: ℹ️ 无需续期操作")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_renew())
