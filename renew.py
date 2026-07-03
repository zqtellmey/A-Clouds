#!/usr/bin/env python3
import asyncio
import os
from playwright.async_api import async_playwright

EMAIL = os.environ.get("ACLCLOUDS_EMAIL", "").strip()
PASSWORD = os.environ.get("ACLCLOUDS_PASSWORD", "").strip()

async def run_renew():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
        page = await context.new_page()

        print("[INFO] 访问登录页...")
        await page.goto("https://dash.aclclouds.com/auth/login", wait_until="networkidle")
        
        # 使用 ID 定位输入框 (最稳健)
        print("[INFO] 填充凭证...")
        await page.locator("#username").fill(EMAIL)
        await page.locator("#password").fill(PASSWORD)
        
        # 使用 role 和 class 定位验证码 checkbox
        # .auth-captcha-inner[role="checkbox"] 是你之前确认过的，结合它内部的 checkbox class
        captcha = page.locator('div.auth-captcha-inner[role="checkbox"]')
        print("[INFO] 点击验证码...")
        await captcha.click()
        
        # 等待验证状态变更为已勾选
        await page.wait_for_selector('div.auth-captcha-inner[aria-checked="true"]', timeout=15000)
        print("[INFO] ✅ 验证码已通过")

        # 使用类型定位按钮 (稳健，不依赖 XPATH 路径)
        print("[INFO] 提交登录...")
        await page.locator('button[type="submit"]').click()
        
        # 等待跳转完成
        await page.wait_for_load_state("networkidle")
        
        # 验证是否进入后台
        if "dashboard" in page.url or "client" in page.url:
            print("[INFO] 登录成功，执行续期...")
            
            # 使用登录后的上下文直接调用 API
            projects_resp = await context.request.get("https://dash.aclclouds.com/api/client")
            projects = projects_resp.json().get("data", [])

            for project in projects:
                p_id = project['attributes']['identifier']
                # 如果还需要验证码 token，这里可以从 cookies 或之前的响应提取
                res = await context.request.post(f"https://dash.aclclouds.com/api/client/servers/{p_id}/upgrade/renew")
                if res.ok:
                    print(f"[INFO] ✅ 项目 {p_id} 续期成功")
                else:
                    print(f"[ERROR] 项目 {p_id} 续期失败: {await res.text()}")
        else:
            print("[ERROR] 登录失败，截图保存...")
            await page.screenshot(path="login_failed.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_renew())
