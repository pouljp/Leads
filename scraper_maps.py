from playwright.sync_api import sync_playwright
import time
import re

def limpar_texto(texto):
    if not texto:
        return texto

    texto = re.sub(r'^[^\w(]+', '', texto)
    texto = texto.replace("\n", " ").replace("\r", " ")
    texto = re.sub(r'\s+', ' ', texto)

    return texto.strip()

def buscar_maps(atividade, cidade, limite=20, enriquecer=False):

    empresas = []
    termo = f"{atividade} em {cidade}"

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir="perfil_google",
            headless=False,
            slow_mo=60
        )

        page = context.new_page()
        page.goto(f"https://www.google.com/maps/search/{termo}", timeout=60000)

        print("\n👉 Se aparecer CAPTCHA, resolva.")
        print("👉 Quando carregar resultados, pressione ENTER.")
        input()

        page.wait_for_selector('div[role="article"]', timeout=30000)

        scroll_div = page.locator('div[role="feed"]')

        ultimo_total = 0

        while True:
            scroll_div.evaluate("el => el.scrollTop = el.scrollHeight")
            time.sleep(2)

            cards = page.query_selector_all('div[role="article"]')
            total_atual = len(cards)

            print("Empresas carregadas:", total_atual)

            if total_atual >= limite:
                break

            # se não carregou novas, para
            if total_atual == ultimo_total:
                break

            ultimo_total = total_atual

        cards = page.query_selector_all('div[role="article"]')

        for i, card in enumerate(cards):
            if i >= limite:
                break

            try:
                card.click()
                time.sleep(3)

                nome = page.query_selector('h1[class*="DUwDvf"]')
                nome = nome.inner_text() if nome else ""

                telefone = ""
                tel = page.query_selector('button[data-item-id^="phone"]')
                if tel:
                    telefone = tel.inner_text()

                endereco = ""
                end = page.query_selector('button[data-item-id="address"]')
                if end:
                    endereco = end.inner_text()

                empresas.append({
                    "nome": limpar_texto(nome),
                    "telefone": limpar_texto(telefone),
                    "endereco": limpar_texto(endereco),
                    "site": "",
                    "instagram": "",
                    "maps": page.url,
                    "horario": "",
                    "avaliacao": "",
                    "reviews": "",
                    "preco": ""
                })

                time.sleep(2)

            except Exception as e:
                print("Erro:", e)

        context.close()

    return empresas