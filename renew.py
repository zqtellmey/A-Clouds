# --- 操作阶段：优化点击逻辑 ---
                renew_btn = page.locator('button.client-btn--secondary:has-text("Renew")')
                if await renew_btn.count() > 0:
                    print(f"[LOG] 找到服务器 {s_name} 的 Renew 按钮，准备尝试强制点击")
                    
                    # 方式 1: 确保按钮可见后直接点击
                    # 方式 2: 如果普通 click 无效，我们使用 evaluate 通过 JS 强制触发点击
                    try:
                        # 先尝试滚动到按钮并确保点击
                        await renew_btn.scroll_into_view_if_needed()
                        # 尝试普通点击
                        await renew_btn.click(timeout=5000)
                    except:
                        # 强制执行 JS 点击，绕过 Playwright 点击坐标的局限
                        await renew_btn.evaluate("el => el.click()")
                    
                    # 等待一下，给界面反应时间
                    await asyncio.sleep(2) 
                    
                    # 截图查看点击后的状态
                    await page.screenshot(path="click_renew_v2.png")
                    send_tg_photo(f"已强制尝试点击 {s_name} 的 Renew 按钮", "click_renew_v2.png")
