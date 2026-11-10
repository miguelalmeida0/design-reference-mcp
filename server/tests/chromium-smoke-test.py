"""Real browser smoke test, no network access required."""
import asyncio
from playwright.async_api import async_playwright
from app.browsing import measure_motion


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content('<style>button{transition:transform 1s}button:hover{transform:translateX(100px)}</style><button>Inspect</button>')
        result = await measure_motion(page)
        assert result["measured"] is True, result
        await page.screenshot(path="chromium-smoke.png")
        await browser.close()
        print("Chromium capture and real CSS motion probe PASS")


if __name__ == "__main__":
    asyncio.run(main())

