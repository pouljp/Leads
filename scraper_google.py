from playwright.sync_api import sync_playwright
import time
import random

def enriquecer_serp(nome_empresa, cidade):
    dados = {}

    termo = f"{nome_empresa} {cidade}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=50)

        context = browser.new_context(
            locale="pt-BR",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            )
        )

        page = context.new_page()
        page.goto(
            f"https://www.google.com/search?q={termo}",
            timeout=60000
        )

        time.sleep(random.uniform(3, 6))

        for link in page.query_selector_all("a"):
            href = link.get_attribute("href")
            if href and "instagram.com" in href:
                dados["instagram"] = href
                break

        for span in page.query_selector_all("span"):
            texto = span.inner_text()
            if "(" in texto and ")" in texto and "-" in texto:
                dados["telefone_extra"] = texto
                break

        browser.close()

    return dados