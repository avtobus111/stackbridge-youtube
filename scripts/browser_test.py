"""Browser regression against a running app. Install playwright; use --channel msedge on Windows."""

import argparse
import json
import secrets
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def wait_images(page):
    page.locator("img[loading]").evaluate_all("imgs=>imgs.forEach(i=>i.loading='eager')")
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if page.locator(".thumbnail img").evaluate_all(
            "imgs=>imgs.length>0&&imgs.every(i=>i.complete&&i.naturalWidth>0)"
        ):
            return
        page.wait_for_timeout(100)
    raise AssertionError("Thumbnail images did not load")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--channel", default=None)
    parser.add_argument("--screenshots", type=Path, default=Path("runtime/screenshots"))
    args = parser.parse_args()
    args.screenshots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=args.channel, headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.base, wait_until="networkidle")
        page.locator(".video-card").first.wait_for()
        wait_images(page)
        page.screenshot(path=str(args.screenshots / "home-desktop.png"), full_page=True)
        # Real title search and clear navigation.
        page.locator("#search-form input").fill("горы")
        page.locator("#search-form").press("Enter")
        expect(page.locator(".page-heading")).to_contain_text("горы")
        expect(page.locator(".video-card")).not_to_have_count(0)
        page.goto(args.base, wait_until="networkidle")
        page.locator('.header-actions [data-action="login"]').click()
        page.locator('#dialog [data-action="register"]').click()
        handle = "browser_" + secrets.token_hex(4)
        page.locator('#dialog input[name="name"]').fill("Браузерная проверка")
        page.locator('#dialog input[name="handle"]').fill(handle)
        page.locator('#dialog input[name="password"]').fill(secrets.token_urlsafe(18))
        page.get_by_role("button", name="Создать аккаунт", exact=True).click()
        expect(page.locator(".account-button")).to_be_visible()
        page.locator('.header-actions a[href="/upload"]').click()
        page.locator('input[type="file"]').set_input_files(
            Path(__file__).resolve().parent.parent / "assets/demo/01.mp4"
        )
        page.locator('input[name="title"]').fill("Проверка загрузки в браузере")
        page.locator('select[name="visibility"]').select_option("private")
        page.locator('#upload-form button[type="submit"]').click()
        expect(page).to_have_url(args.base + "/studio", timeout=30000)
        expect(page.locator(".studio-item .status.ready")).to_be_visible(timeout=90000)
        page.locator(".studio-copy h2 a").first.click()
        player = page.locator("#video-player")
        player.evaluate("(v)=>v.play()")
        page.wait_for_timeout(1500)
        assert player.evaluate("(v)=>v.currentTime") > 0.2, "Video playback did not advance"
        page.locator('[data-action="like"]').click()
        expect(page.locator('[data-action="like"]')).to_have_attribute("aria-pressed", "true")
        body = "Проверено в браузере <img src=x onerror=alert(1)>"
        page.locator(".comment-form textarea").fill(body)
        page.locator(".comment-form button").click()
        expect(page.locator(".comment-text").first).to_have_text(body)
        assert page.locator(".comment-text img").count() == 0, "Stored comment must be rendered as text"
        page.locator('[data-action="save"]').click()
        page.locator('#dialog [data-action="new-playlist"]').click()
        page.locator('#dialog input[name="title"]').fill("Браузерная подборка")
        page.locator("#dialog form button").click()
        expect(page.locator("#dialog")).not_to_be_visible()
        page.screenshot(path=str(args.screenshots / "watch-desktop.png"), full_page=True)
        page.goto(args.base + "/studio", wait_until="networkidle")
        page.locator('[data-action="grants"]').click()
        page.locator("#dialog textarea").fill("viewer")
        page.locator("#dialog form button").click()
        expect(page.locator("#dialog")).not_to_be_visible()
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(args.base, wait_until="networkidle")
        page.locator(".video-card").first.wait_for()
        wait_images(page)
        assert not page.evaluate("document.documentElement.scrollWidth>innerWidth"), (
            "Horizontal overflow on mobile"
        )
        assert not page.locator(".sidebar .nav-copy").is_visible(), (
            "Desktop login prompt overlaps mobile navigation"
        )
        page.screenshot(path=str(args.screenshots / "home-mobile.png"), full_page=True)
        page.goto(args.base + "/docs", wait_until="networkidle")
        expect(page.locator(".swagger-ui .info .title")).to_contain_text("StackBridge")
        assert not errors, errors
        print(
            json.dumps(
                {
                    "passed": True,
                    "javascript_errors": errors,
                    "scenarios": [
                        "search",
                        "signup",
                        "upload",
                        "processing",
                        "playback",
                        "like",
                        "comment XSS",
                        "playlist",
                        "private grants",
                        "mobile",
                        "local Swagger",
                    ],
                }
            )
        )
        browser.close()


if __name__ == "__main__":
    main()
