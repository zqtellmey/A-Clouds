#!/usr/bin/env python3
import asyncio
import os
import base64
import requests
from datetime import datetime, timezone
from playwright.async_api import async_playwright

# 环境变量读取
EMAIL = os.environ.get("ACLCLOUDS_EMAIL", "").strip()
PASSWORD = os.environ.get("ACLCLOUDS_PASSWORD", "").strip()
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "").strip()
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

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

async def ask_groq_for_captcha(image_bytes_list, target_word, max_retries=3):
    """
    使用 Groq API（OpenAI 兼容多模态格式）一次性将 4 张图片传给模型，内置自动重试机制
    """
    if not GROQ_API_KEY:
        print("[ERROR] 未配置 GROQ_API_KEY 环境变量，无法识别验证码图片！")
        return None
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    content_parts = [
        {"type": "text", "text": f"These 4 images are options 1, 2, 3, and 4. Which one of these images represents, contains, or matches the concept/word '{target_word}'? Answer ONLY with the number of the correct image (1, 2, 3, or 4)."}
    ]
    
    for idx, img_bytes in enumerate(image_bytes_list):
        b64_data = base64.b64encode(img_bytes).decode('utf-8')
        content_parts.append({"type": "text", "text": f"Option {idx + 1}:"})
        content_parts.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{b64_data}"
            }
        })
        
    payload = {
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "messages": [
            {
                "role": "user",
                "content": content_parts
            }
        ],
        "max_tokens": 10
    }
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 增加自动重试循环
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[INFO] 正在将 4 张验证码图片一次性打包发送给 Groq (目标: {target_word}) [尝试 {attempt}/{max_retries}]...")
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code == 200:
                res_json = response.json()
                text = res_json['choices'][0]['message']['content'].strip()
                print(f"[INFO] Groq 返回结果: {text}")
                
                for char in text:
                    if char in ['1', '2', '3', '4']:
                        choice_idx = int(char) - 1
                        print(f"[INFO] 成功解析出正确选项索引: {choice_idx} (对应第 {char} 张)")
                        return choice_idx
                        
                print(f"[ERROR] 未能从 Groq 返回结果中提取到有效编号: {text}")
            else:
                print(f"[ERROR] Groq API 请求失败: {response.text}")
        except Exception as e:
            print(f"[ERROR] 调用 Groq API 异常 (尝试 {attempt}/{max_retries}): {e}")
        
        if attempt < max_retries:
            print("[INFO] 等待 2 秒后进行重试...")
            await asyncio.sleep(2)
        
    return None

async def run_renew():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale="zh-CN"
        )
        page = await context.new_page()

        # --- 登录部分 (已集成智能图形验证处理) ---
        print("[INFO] 访问登录页...")
        await page.goto("https://dash.aclclouds.com/auth/login", wait_until="networkidle")
        await page.screenshot(path="step1.png")
        send_tg_photo("已进入登录页", "step1.png")

        print("[INFO] 填充凭证...")
        await page.locator("#username").fill(EMAIL)
        await page.locator("#password").fill(PASSWORD)
        
        print("[INFO] 点击验证码...")
        captcha_container = page.locator('div.auth-captcha-inner[role="checkbox"]')
        await captcha_container.click()
        
        # 检查 aria-checked 属性判断是否直接打勾，或是弹出了图片选择框
        try:
            await page.wait_for_selector('div.auth-captcha-inner[role="checkbox"][aria-checked="true"]', timeout=3000)
            print("[INFO] 验证码直接打勾通过！")
        except:
            print("[INFO] 未直接打勾，检测到图形验证弹窗，开始使用 Groq API 一次性识别...")
            prompt_locator = page.locator('div.auth-captcha-prompt strong')
            if await prompt_locator.count() > 0:
                target_word = await prompt_locator.inner_text()
                print(f"[INFO] 目标验证词汇: {target_word}")
                
                option_buttons = page.locator('button.auth-captcha-option')
                count = await option_buttons.count()
                if count == 4:
                    image_bytes_list = []
                    for i in range(4):
                        img_element = option_buttons.nth(i).locator('img.auth-captcha-option-img')
                        img_bytes = await img_element.screenshot(type="jpeg", quality=40)
                        image_bytes_list.append(img_bytes)
                    
                    correct_index = await ask_groq_for_captcha(image_bytes_list, target_word)
                    if correct_index is not None and 0 <= correct_index < 4:
                        print(f"[INFO] 准备点击第 {correct_index + 1} 个选项")
                        await option_buttons.nth(correct_index).click()
                        try:
                            await page.wait_for_selector('div.auth-captcha-inner[role="checkbox"][aria-checked="true"]', timeout=15000)
                        except:
                            print("[ERROR] 点击选项后验证码仍未勾选成功")
                    else:
                        print("[ERROR] 未能通过 Groq 正确识别出验证选项")

        # 检查最终是否成功打勾，如果未打勾则直接终止后续所有操作
        checkbox_elem = page.locator('div.auth-captcha-inner[role="checkbox"]')
        is_checked = await checkbox_elem.get_attribute("aria-checked")
        if is_checked != "true":
            print("[ERROR] 人机验证未通过，终止后续所有操作。")
            send_tg_msg("登录失败：人机验证未通过，流程已终止。")
            await browser.close()
            return

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

        # 1. 统一进入项目页
        await page.goto("https://aclclouds.com/dashboard/projects", wait_until="networkidle")
        
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
