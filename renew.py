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
        final_text = f"**ACLClouds**\n{text}"
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

    batches = [
        ([0], 0),          
        ([1, 2, 3], 1)     
    ]

    for idx_group, (img_indices, base_offset) in enumerate(batches):
        if idx_group > 0:
            await asyncio.sleep(6)

        max_option_num = len(img_indices)
        if idx_group == 0:
            prompt_text = f"Target: '{target_word}'. Does this image match the target? Answer '1' if it matches, or '0' if it does NOT match. Answer ONLY 1 or 0 at the very end after reasoning."
        else:
            prompt_text = f"Target: '{target_word}'. Look at these 3 options. Which option number (1, 2, or 3) is correct? Answer ONLY the single digit 1, 2, or 3 at the very end after reasoning."

        content_parts = [
            {"type": "text", "text": prompt_text}
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
            "model": "qwen/qwen3.8-27b",  # 已更新为当前支持的最新模型名称
            "messages": [{"role": "user", "content": content_parts}],
            "max_tokens": 1000,
            "temperature": 0
        }

        for attempt in range(1, max_retries + 1):
            try:
                print(f"[INFO] 正在向 Groq 发送第 {idx_group + 1} 组图片进行识别 (目标: {target_word})...")
                response = requests.post(url, json=payload, headers=headers, timeout=30)
                print(f"[INFO] Groq 响应状态码: {response.status_code}")
                
                if response.status_code == 200:
                    res_json = response.json()
                    raw_text = res_json['choices'][0]['message']['content'].strip()
                    
                    print(f"--- Groq 原始内容开始 (第 {idx_group + 1} 组) ---\n{raw_text}\n--- Groq 原始内容结束 ---")
                    send_tg_msg(f"**Groq 识别调试 (第 {idx_group + 1} 组)**\n目标: `{target_word}`\n
