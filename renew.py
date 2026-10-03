#!/usr/bin/env python3
import asyncio
import os
import requests
from datetime import datetime, timezone
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
            requests.post(url, data={'chat_id': TG_CHAT_ID, 'caption': f"ACLClouds: {caption}"}, files={'photo': f})
    except Exception as e:
        print(f"[ERROR] TG 推送失败: {e}")

def send_tg_msg(text):
    if TG_BOT_TOKEN and TG_CHAT_ID:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TG_CHAT_ID, "text": f"**ACLClouds**\n{text}", "parse_mode": "HTML"})

async def handle_captcha(page, is_dialog=False):
    """
    处理基于 Shadow DOM 的 Cap 验证
    """
    base_locator = page.locator('div[role="dialog"]') if is_dialog else page
    
    try:
        print("[INFO] 正在寻找并点击 Cap 验证框...")
        # Cap 验证组件包含在 shadow dom 中，可以通过 locator 直接穿透或定位内部的触发器
        captcha_trigger = base_locator.locator('cap-widget div.captcha-trigger')
        await captcha_trigger.waitFor(state="visible", timeout=10000)
        await captcha_trigger.click()
        
        # 等待验证完成（观察 data-state 属性变为 done）
        print("[INFO] 等待 Cap 验证通过...")
        await asyncio.sleep(4)
        
        # 截图保存状态
        await page.screenshot(path="step_captcha_result.png")
        send_tg_photo("Cap 验证交互后的状态", "step_captcha_result.png")
        
        # 检查是否成功通过（根据样式或属性判断，通常 data-state="done" 表示通过）
        captcha_widget = base_locator.locator('cap-widget div.captcha')
        state = await captcha_widget.get_attribute("data-state")
        if state == "done":
            print("[INFO] Cap 验证成功通过！")
            return True
        else:
            print(f"[WARNING] Cap 验证状态未知或未完成: {state}")
            return True # 部分情况下可能直接通过，返回 True 让外层后续逻辑继续尝试
    except Exception as e:
        print(f"[ERROR] 处理 Cap 验证异常: {e}")
        return False

async def run_renew():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale="zh-CN"
        )
        page = await context.new_page()
        await page.goto("https://dash.aclclouds.com/auth/login", wait_until="networkidle")
        await page.screenshot(path="step1.png")
        send_tg_photo("1. 已进入登录页", "step1.png")
        
        await page.locator("#username").fill(EMAIL)
        await page.locator("#password").fill(PASSWORD)
        await asyncio.sleep(1)
        await page.screenshot(path="step_fill_auth.png")
        send_tg_photo("2. 已填充账号密码", "step_fill_auth.png")
        
        # 执行 Cap 验证
        await handle_captcha(page, is_dialog=False)
        
        await page.screenshot(path="step2.png")
        send_tg_photo("3. 验证码交互已完成", "step2.png")
        
        await page.locator("#password").press("Enter")
        try:
            await page.wait_for_url("**/dashboard*", timeout=20000)
            await page.wait_for_load_state("networkidle")
        except:
            pass
        
        await asyncio.sleep(2)
        await page.screenshot(path="step3.png")
        send_tg_photo("4. 登录完成后控制台页面", "step3.png")
        
        await page.goto("https://aclclouds.com/dashboard/projects", wait_until="networkidle")
        reactivate_btns = page.locator('button:has-text("Reactivate")')
        r_count = await reactivate_btns.count()
        if r_count > 0:
            for i in range(r_count):
                print(f"[INFO] 正在执行第 {i+1} 个 Reactivate...")
                await reactivate_btns.nth(i).click()
                await asyncio.sleep(2)
                
                reactivate_success = await handle_captcha(page, is_dialog=True)
                if reactivate_success:
                    print(f"[INFO] 第 {i+1} 个 Reactivate 验证通过！")
                else:
                    print(f"[WARNING] 第 {i+1} 个 Reactivate 验证未通过或超时")
                    
                await asyncio.sleep(2)
                await page.screenshot(path=f"react_final_{i}.png")
                send_tg_photo(f"已执行 Reactivate 动作 {i+1} 及验证", f"react_final_{i}.png")
                await asyncio.sleep(3)
                
        resp = await context.request.get("https://dash.aclclouds.com/api/client")
        if resp.ok:
            servers = (await resp.json()).get("data", [])
            now = datetime.now(timezone.utc)
            for server in servers:
                attrs = server['attributes']
                s_name = attrs['name']
                hours_left = (datetime.fromisoformat(attrs['expires_at']) - now).total_seconds() / 3600
                if hours_left < 2:
                    renew_btn = page.locator('button.client-btn--secondary:has-text("Renew")').first
                    if await renew_btn.count() > 0:
                        await renew_btn.scroll_into_view_if_needed()
                        await renew_btn.evaluate("el => el.click()")
                        await asyncio.sleep(2)
                        await handle_captcha(page, is_dialog=True)
                        await asyncio.sleep(2)
                        await page.screenshot(path="renew_final_result.png")
                        send_tg_photo(f"已尝试完成 {s_name} 的 Renew 交互式验证", "renew_final_result.png")
                        await asyncio.sleep(5)
                        new_resp = await context.request.get("https://dash.aclclouds.com/api/client")
                        if new_resp.ok:
                            for n_s in (await new_resp.json()).get("data", []):
                                if n_s['attributes']['name'] == s_name:
                                    n_h = (datetime.fromisoformat(n_s['attributes']['expires_at']) - now).total_seconds() / 3600
                                    send_tg_msg(f"服务器: {s_name}\n状态: ✅ 续期后剩余时间: {n_h:.2f} 小时")
                    else:
                        await page.screenshot(path="not_found.png")
                        send_tg_photo(f"服务器 {s_name} 剩余 {hours_left:.2f} 小时，但未找到 Renew 按钮！", "not_found.png")
                else:
                    send_tg_msg(f"服务器: {s_name}\n剩余时间: {hours_left:.2f} 小时\n状态: ℹ️ 无需续期操作")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_renew())
