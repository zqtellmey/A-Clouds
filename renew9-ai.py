#!/usr/bin/env python3
import asyncio
import os
import base64
import re
import requests
from io import BytesIO
from PIL import Image
from datetime import datetime, timezone
from playwright.async_api import async_playwright

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
            requests.post(url, data={'chat_id': TG_CHAT_ID, 'caption': f"ACLClouds: {caption}"}, files={'photo': f})
    except Exception as e:
        print(f"[ERROR] TG 推送失败: {e}")

def send_tg_msg(text):
    if TG_BOT_TOKEN and TG_CHAT_ID:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TG_CHAT_ID, "text": f"<b>ACLClouds</b>\n{text}", "parse_mode": "HTML"})

def ensure_min_image_size(img_bytes, min_size=32):
    try:
        with Image.open(BytesIO(img_bytes)) as img:
            width, height = img.size
            if width < min_size or height < min_size:
                new_w = max(width, min_size)
                new_h = max(height, min_size)
                resized_img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                output = BytesIO()
                resized_img.save(output, format="JPEG", quality=80)
                return output.getvalue()
    except Exception as e:
        print(f"[WARNING] 处理图片尺寸异常: {e}")
    return img_bytes

def send_combined_options_preview(image_bytes_list, target_word):
    try:
        images = [Image.open(BytesIO(b)) for b in image_bytes_list]
        widths, heights = zip(*(i.size for i in images))
        total_width = sum(widths) + 30
        max_height = max(heights) + 40
        combined = Image.new('RGB', (total_width, max_height), (240, 240, 240))
        x_offset = 10
        for idx, img in enumerate(images):
            combined.paste(img, (x_offset, 30))
            x_offset += img.width + 10
        preview_path = "captcha_options_preview.png"
        combined.save(preview_path)
        send_tg_photo(f"验证码选项合集 (目标: {target_word}) [图 1,2,3,4]", preview_path)
    except Exception as e:
        print(f"[WARNING] 拼接预览图失败: {e}")

async def ask_groq_for_captcha(image_bytes_list, target_word, max_retries=3):
    if not GROQ_API_KEY:
        print("[ERROR] 未配置 GROQ_API_KEY")
        return None
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    batches = [([0], 0), ([1, 2, 3], 1)]
    for idx_group, (img_indices, base_offset) in enumerate(batches):
        if idx_group > 0:
            await asyncio.sleep(6)
        max_option_num = len(img_indices)
        prompt_text = f"Target: '{target_word}'. Does this image match the target? Answer '1' if it matches, or '0' if it does NOT match. Answer ONLY 1 or 0 at the very end after reasoning." if idx_group == 0 else f"Target: '{target_word}'. Look at these 3 options. Which option number (1, 2, or 3) is correct? Answer ONLY the single digit 1, 2, or 3 at the very end after reasoning."
        content_parts = [{"type": "text", "text": prompt_text}]
        for local_idx, global_idx in enumerate(img_indices):
            b64_data = base64.b64encode(image_bytes_list[global_idx]).decode('utf-8')
            content_parts.extend([{"type": "text", "text": f"Option {local_idx + 1}:"}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_data}"}}])
        payload = {"model": "qwen/qwen3.8-27b", "messages": [{"role": "user", "content": content_parts}], "max_tokens": 1000, "temperature": 0}
        for attempt in range(1, max_retries + 1):
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=30)
                if response.status_code == 200:
                    raw_text = response.json()['choices'][0]['message']['content'].strip()
                    send_tg_msg(f"<b>Groq 识别调试 (第 {idx_group + 1} 组)</b>\n目标: <code>{target_word}</code>\n<pre>{raw_text}</pre>")
                    clean_text = raw_text.split("</think>")[-1].strip() if "</think>" in raw_text else raw_text.strip()
                    if idx_group == 0:
                        matches = re.findall(r'\b([01])\b', clean_text)
                        if matches and matches[-1] == '1':
                            return 0
                        else:
                            break
                    else:
                        matches = re.findall(rf'\b([1-{max_option_num}])\b', clean_text)
                        if matches:
                            return base_offset + (int(matches[-1]) - 1)
                    break
                elif response.status_code == 429:
                    await asyncio.sleep(10 * attempt)
            except Exception as e:
                print(f"[ERROR] 调用 Groq 异常: {e}")
            if attempt < max_retries:
                await asyncio.sleep(3)
    return None

async def handle_captcha(page, is_dialog=False):
    base_locator = page.locator('div[role="dialog"]') if is_dialog else page
    await base_locator.locator('div.auth-captcha-inner[role="checkbox"]').click()
    await asyncio.sleep(3)
    await page.screenshot(path="step_captcha_click.png")
    send_tg_photo("点击验证码勾选框后的状态", "step_captcha_click.png")
    try:
        if await base_locator.locator('div.auth-captcha-inner[role="checkbox"]').get_attribute("aria-checked") == "true":
            return True
    except:
        if is_dialog and await page.locator('div[role="dialog"]').count() == 0:
            return True
    prompt_locator = base_locator.locator('div.auth-captcha-prompt strong')
    try:
        await prompt_locator.wait_for(state="visible", timeout=6000)
    except:
        pass
    if await prompt_locator.count() > 0:
        target_word = await prompt_locator.inner_text()
        await page.screenshot(path="step_captcha_dialog.png")
        send_tg_photo(f"已弹出验证图形弹窗 (目标: {target_word})", "step_captcha_dialog.png")
        option_buttons = base_locator.locator('button.auth-captcha-option')
        if await option_buttons.count() == 4:
            image_bytes_list = [ensure_min_image_size(await option_buttons.nth(i).locator('img.auth-captcha-option-img').screenshot(type="jpeg", quality=80), 32) for i in range(4)]
            send_combined_options_preview(image_bytes_list, target_word)
            correct_index = await ask_groq_for_captcha(image_bytes_list, target_word)
            if correct_index is not None and 0 <= correct_index < 4:
                await option_buttons.nth(correct_index).click()
                await asyncio.sleep(3)
                await page.screenshot(path="step_after_option_click.png")
                send_tg_photo(f"已点击第 {correct_index + 1} 个选项后的页面状态", "step_after_option_click.png")
                if is_dialog and await page.locator('div[role="dialog"]').count() == 0:
                    return True
                try:
                    await base_locator.locator('div.auth-captcha-inner[role="checkbox"][aria-checked="true"]').wait_for(state="visible", timeout=10000)
                    return True
                except:
                    if is_dialog and await page.locator('div[role="dialog"]').count() == 0:
                        return True
    if is_dialog and await page.locator('div[role="dialog"]').count() == 0:
        return True
    try:
        return await base_locator.locator('div.auth-captcha-inner[role="checkbox"]').get_attribute("aria-checked") == "true"
    except:
        return is_dialog

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
        await handle_captcha(page, is_dialog=False)
        if await page.locator('div.auth-captcha-inner[role="checkbox"]').get_attribute("aria-checked") != "true":
            await page.screenshot(path="step_login_failed.png")
            send_tg_photo("❌ 人机验证失败终止画面", "step_login_failed.png")
            send_tg_msg("登录失败：人机验证未通过，流程已终止。")
            await browser.close()
            return
        await page.screenshot(path="step2.png")
        send_tg_photo("3. 验证码已成功打勾", "step2.png")
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
                
                # 复用和 Renew 一样的通用人机验证弹窗处理流程
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
