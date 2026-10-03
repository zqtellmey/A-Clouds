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
        # 兼容处理：如果没有 dialog 或者 dialog 已经关闭，则退回到整个 page 查找
        if is_dialog and await page.locator('div[role="dialog"]').count() == 0:
            base_locator = page
            
        captcha_trigger = base_locator.locator('cap-widget div.captcha-trigger')
        await captcha_trigger.wait_for(state="visible", timeout=10000)
        await captcha_trigger.click()
        
        print("[INFO] 等待 Cap 验证通过...")
        await asyncio.sleep(4)
        
        await page.screenshot(path="step_captcha_result.png")
        send_tg_photo("Cap 验证交互后的状态", "step_captcha_result.png")
        
        # 尝试检查状态，若找不到弹窗或 widget 则直接认为点击动作完成，交由 API 结果校验
        try:
            captcha_widget = base_locator.locator('cap-widget div.captcha')
            state = await captcha_widget.get_attribute("data-state", timeout=3000)
            if state == "done":
                print("[INFO] Cap 验证状态显示已完成！")
        except:
            print("[INFO] 验证框已关闭或无状态属性，继续执行...")
            
        return True
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
        
        # 执行登录页的 Cap 验证
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
        
        # 通过 API 获取服务器列表
        resp = await context.request.get("https://dash.aclclouds.com/api/client")
        if resp.ok:
            servers = (await resp.json()).get("data", [])
            now = datetime.now(timezone.utc)
            for server in servers:
                attrs = server['attributes']
                s_name = attrs['name']
                s_id = attrs.get('identifier') or attrs.get('uuid') or server.get('id')
                if not s_id:
                    continue
                
                expires_at = attrs.get('expires_at')
                hours_left = 999.0
                if expires_at:
                    hours_left = (datetime.fromisoformat(expires_at) - now).total_seconds() / 3600
                
                print(f"[INFO] 检查服务器: {s_name} (剩余时间: {hours_left:.2f} 小时)")
                
                # 如果小于 2 小时，或者本身处于过期/需要续期状态
                if hours_left < 2:
                    server_url = f"https://aclclouds.com/server/{s_id}"
                    await page.goto(server_url, wait_until="networkidle")
                    await asyncio.sleep(2)
                    
                    # 寻找激活或续期按钮
                    action_btn = page.locator('button:has-text("Renouveler"), button:has-text("Reactivate"), button:has-text("Renew")').first
                    
                    if await action_btn.count() > 0 and await action_btn.is_visible():
                        print(f"[INFO] 发现服务器 {s_name} 的续期/激活按钮，正在点击...")
                        old_expires_at = expires_at
                        
                        await action_btn.scroll_into_view_if_needed()
                        await action_btn.click()
                        await asyncio.sleep(2)
                        
                        # 处理人机验证
                        await handle_captcha(page, is_dialog=True)
                        await asyncio.sleep(5) # 等待后端处理
                        
                        # 【核心优化】：通过请求 API 获取最新数据对比 expires_at 是否更新，以此判断是否真正续期成功
                        success = False
                        new_hours_left = hours_left
                        new_resp = await context.request.get("https://dash.aclclouds.com/api/client")
                        if new_resp.ok:
                            for n_s in (await new_resp.json()).get("data", []):
                                if (n_s['attributes'].get('identifier') or n_s['attributes'].get('uuid') or n_s.get('id')) == s_id:
                                    new_expires_at = n_s['attributes'].get('expires_at')
                                    new_hours_left = (datetime.fromisoformat(new_expires_at) - now).total_seconds() / 3600
                                    if new_expires_at != old_expires_at:
                                        success = True
                                    break
                        
                        if success:
                            print(f"[INFO] 服务器 {s_name} 续期/激活成功！更新后剩余时间: {new_hours_left:.2f} 小时")
                            send_tg_msg(f"服务器: {s_name}\n状态: ✅ 续期/激活成功\n剩余时间: {new_hours_left:.2f} 小时")
                        else:
                            print(f"[WARNING] 服务器 {s_name} 续期后时间未发生变化")
                            send_tg_msg(f"服务器: {s_name}\n状态: ⚠️ 续期请求已发出，但过期时间未变")
                            
                        await page.screenshot(path=f"server_{s_id}_result.png")
                        send_tg_photo(f"已执行服务器 {s_name} 的续期交互", f"server_{s_id}_result.png")
                    else:
                        print(f"[INFO] 服务器 {s_name} 未找到可用的续期/激活按钮")
                else:
                    send_tg_msg(f"服务器: {s_name}\n剩余时间: {hours_left:.2f} 小时\n状态: ℹ️ 无需续期操作")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_renew())
