import asyncio
from playwright.async_api import async_playwright
import re

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # 模拟真实浏览器
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        # 1. 访问并等待挑战通过 (Didomi/WP)
        try:
            print("Navigating to https://efe.com/portada-espana/...")
            await page.goto("https://efe.com/portada-espana/", timeout=90000)
            await asyncio.sleep(12) # 强力驻留
            
            # 点击处理可能存在的 Consent
            try:
                await page.click("button.is-primary, button#didomi-notice-agree-button", timeout=5000)
                print("Consent clicked.")
            except:
                pass
            
            # 取出标题和链接
            titles = await page.get_by_role("heading").all()
            print(f"Total Headings: {len(titles)}")
            
            links = await page.eval_on_selector_all("a", "elements => elements.map(e => e.href)")
            dated = [l for l in set(links) if re.search(r"/\d{4}-\d{2}-\d{2}/", str(l))]
            print(f"DATED_LINKS_PROBED: {len(dated)}")
            for l in dated[:10]:
                print(f"LINK: {l}")
                
        except Exception as e:
            print(f"PROBE_ERROR: {e}")
        await browser.close()

asyncio.run(run())
