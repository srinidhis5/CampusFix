"""Capture real browser predictions: python -m src.capture_ml_screenshots.

Requires requirements-dev.txt and locally installed Google Chrome. No complaints
are submitted. Demo logins create the app's normal demo accounts if absent.
"""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:5001")
    args = parser.parse_args()
    output = ROOT / "reports/screenshots"
    output.mkdir(exist_ok=True)
    evidence = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url + "/login")
        page.locator('form[action$="/demo-login/reporter"] button').click()
        for name, title, description in [
            ("electrical_prediction", "Sparking switch near Block B corridor", "There are small sparks from the switch board and it feels unsafe."),
            ("network_prediction", "WiFi not available in library first floor", "The signal drops often and students cannot access online resources."),
        ]:
            page.locator("#title").fill(title)
            with page.expect_response(lambda response: response.url.endswith("/predict") and response.request.method == "POST") as response_info:
                page.locator("#description").fill(description)
            response = response_info.value
            data = response.json()
            assert response.ok and data["source"] == "trained_model", data
            page.wait_for_function("document.querySelector('#aiSuggestionMessage').textContent.includes('Trained models:')")
            page.screenshot(path=str(output / f"{name}.png"), full_page=True)
            evidence.append({"title": title, "description": description, "response": data, "screenshot": f"{name}.png"})
        page.goto(args.url + "/logout")
        page.goto(args.url + "/login")
        page.locator('form[action$="/demo-login/admin"] button').click()
        page.goto(args.url + "/admin/ml-insights")
        page.get_by_text("Category model comparison", exact=True).wait_for()
        page.screenshot(path=str(output / "ml_insights.png"), full_page=True)
        assert not errors, errors
        browser.close()
    (output / "predictions.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"Saved browser screenshots and actual API responses to {output}")


if __name__ == "__main__":
    main()
