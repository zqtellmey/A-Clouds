#!/usr/bin/env python3
import asyncio
import os
import base64
import re
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
    if not GROQ_API_KEY:
        print("[ERROR] 未配置 GROQ_API_KEY")
        return None
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    # 批次定义：每批 2 张图。base_offset 用于计算全局索引
    batches = [
        ([0, 1], 0),  # 第一组：全局图 0, 1 -> 对应模型眼中的 Option 1, 2
        ([2, 3], 2)   # 第二组：全局图 2, 3 -> 对应模型眼中的 Option 1, 2
    ]

    for idx_group, (img_indices, base_offset) in enumerate(batches):
        if idx_group > 0:
            await asyncio.sleep(8)

        content_parts = [
            {"type": "text", "text": f"Target: '{target_word}'. Which option is correct? Answer ONLY 1 or 2 at the very end."}
        ]
        
        for local_idx, global_idx in enumerate(img_indices):
            img_bytes = image_bytes_list[global_idx]
            b64_data = base64.b64encode(img_bytes).decode('utf-8')
            content_parts.append({"type": "text", "text": f"Option {local_idx + 1}:"})
            content_parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{b64_data}"
                }
            })
            
        payload = {
            "model": "qwen/qwen3.6-27b",
            "messages": [{"role": "user", "content": content_parts}],
            "max_tokens": 50,
            "temperature": 0
        }

        for attempt in range(1, max_retries + 1):
            try:
                print(f"[INFO] 正在向 Groq 发送第 {idx_group + 1} 组图片进行识别...")
                response = requests.post(url, json=payload, headers=headers, timeout=30)
                print(f"[INFO] Groq 响应状态码: {response.status_code}")
                
                if response.status_code == 200:
                    res_json = response.json()
                    raw_text = res_json['choices'][0]['message']['content'].strip()
                    print(f"[INFO] Groq 原始内容返回: {raw_text}")
                    
                    clean_text = raw_text
                    if "</think>" in clean_text:
                        clean_text = clean_text.split("</think>")[-1].strip()
                    
                    # 修复点：通过正则匹配查找文本中所有出现的 1 或 2，取【最后一个】作为最终答案，避开前文序号干扰
                    matches = re.findall(r'\b([12])\b', clean_text)
                    if matches:
                        char = matches[-1]
                        choice_idx = base_offset + (int(char) - 1)
                        print(f"[INFO] 找到正确选项: 全局第 {choice_idx + 1} 个")
                        return choice_idx
                    
                    break
                elif response.status_code == 429:
                    print("[WARNING] 触发 429 频率限制，等待重试...")
                    await asyncio.sleep(12)
                else:
                    print(f"[ERROR] Groq API 请求失败返回: {response.text}")
            except Exception as e:
                print(f"[ERROR] 调用 Groq API 异常: {e}")
            
            if attempt < max_retries:
                await asyncio.sleep(3)
        
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

        print("[INFO] 访问登录页...")
        await page.goto("https://dash.aclclouds.com/auth/login", wait_until="networkidle")
        await page.screenshot(path="step1.png")
        send_tg_photo("已进入登录页", "step1.png")

        print("[INFO] 填充账号密码...")
        await page.locator("#username").fill(EMAIL)
        await page.locator("#password").fill(PASSWORD)
        
        print("[INFO] 点击人机验证勾选框...")
        captcha_container = page.locator('div.auth-captcha-inner[role="checkbox"]')
        await captcha_container.click()
        
        print("[INFO] 等待验证结果或图形弹窗出现...")
        await asyncio.sleep(3)
        
        is_already_checked = await captcha_container.get_attribute("aria-checked")
        if is_already_checked == "true":
            print("[INFO] 验证码直接打勾通过！")
        else:
            print("[INFO] 未直接打勾，开始检测图形验证弹窗...")
            
            prompt_locator = page.locator('div.auth-captcha-prompt strong')
            try:
                await prompt_locator.wait_for(state="visible", timeout=6000)
            except Exception as e:
                print(f"[WARNING] 未能定位到验证码提示词元素: {e}")

            if await prompt_locator.count() > 0:
                target_word = await prompt_locator.inner_text()
                print(f"[INFO] 成功获取目标验证词汇: {target_word}")
                
                option_buttons = page.locator('button.auth-captcha-option')
                count = await option_buttons.count()
                print(f"[INFO] 成功获取到验证码选项数量: {count}")
                
                if count == 4:
                    image_bytes_list = []
                    for i in range(4):
                        img_element = option_buttons.nth(i).locator('img.auth-captcha-option-img')
                        img_bytes = await img_element.screenshot(type="jpeg", quality=40)
                        image_bytes_list.append(img_bytes)
                    print("[INFO] 已成功截取 4 个选项的图片，准备调用 Groq...")
                    
                    correct_index = await ask_groq_for_captcha(image_bytes_list, target_word)
                    if correct_index is not None and 0 <= correct_index < 4:
                        print(f"[INFO] 准备点击第 {correct_index + 1} 个选项")
                        
                        await option_buttons.nth(correct_index).evaluate("el => el.click()")
                        await asyncio.sleep(3)
                        
                        await page.screenshot(path="captcha_clicked.png")
                        send_tg_photo(f"已点击第 {correct_index + 1} 个选项后的页面状态", "captcha_clicked.png")
                        
                        try:
                            await page.wait_for_selector('div.auth-captcha-inner[role="checkbox"][aria-checked="true"]', timeout=10000)
                            print("[INFO] 验证码已成功勾选！")
                        except:
                            print("[WARNING] 点击选项后验证码勾选状态等待超时")
                    else:
                        print("[ERROR] 未能通过 Groq 确认正确选项")
                else:
                    print(f"[ERROR] 选项数量异常，当前获取到: {count}")
            else:
                print("[ERROR] 页面上未找到任何验证码提示词节点")

        checkbox_elem = page.locator('div.auth-captcha-inner[role="checkbox"]')
        is_checked = await checkbox_elem.get_attribute("aria-checked")
        if is_checked != "true":
            print("[ERROR] 人机验证最终未通过，终止后续操作。")
            send_tg_msg("登录失败：人机验证未通过，流程已终止。")
            await browser.close()
            return

        await page.screenshot(path="step2.png")
        send_tg_photo("验证码已打勾", "step2.png")

        print("[INFO] 提交表单...")
        await page.locator("#password").press("Enter")
        
        try:
            await page.wait_for_url("**/dashboard*", timeout=20000)
            await page.wait_for_load_state("networkidle")
        except:
            pass

        await page.screenshot(path="step3.png")
        send_tg_photo("最终登录结果", "step3.png")

        # 1. 统一进入项目页
        await page.goto("https://aclclouds.com/dashboard/projects", wait_until="networkidle")
        
        # 2. 优先处理 Reactivate
        reactivate_btns = page.locator('button:has-text("Reactivate")')
        count = await reactivate_btns.count()
        if count > 0:
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
                
                if hours_left < 2:
                    renew_btn = page.locator('button.client-btn--secondary:has-text("Renew")').first
                    if await renew_btn.count() > 0:
                        await renew_btn.scroll_into_view_if_needed()
                        await renew_btn.evaluate("el => el.click()")
                        await asyncio.sleep(2)
                        checkbox = page.locator('div[role="checkbox"]:has-text("I am not a robot")')
                        if await checkbox.count() > 0: await checkbox.click()
                        await asyncio.sleep(1)
                        target_btn = page.locator('div[role="dialog"] button:has-text("Serveur")')
                        if await target_btn.count() > 0: await target_btn.click()
                        
                        await asyncio.sleep(2)
                        await page.screenshot(path="renew_final_result.png")
                        send_tg_photo(f"已尝试完成 {s_name} 的 Renew 交互式验证", "renew_final_result.png")
                        
                        await asyncio.sleep(5)
                        new_resp = await context.request.get("https://dash.aclclouds.com/api/client")
                        if new_resp.ok:
                            new_data = await new_resp.json()
                            for n_s in new_data.get("data", []):
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
