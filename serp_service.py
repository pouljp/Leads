import re as regex

from playwright.sync_api import sync_playwright
from urllib.parse import urlparse, parse_qs
import time
import random
from urllib.parse import quote_plus
import unicodedata
from urllib.parse import quote_plus

def limpar_link_google(href):
    if href and "/url?" in href:
        parsed = urlparse(href)
        query = parse_qs(parsed.query)
        if "q" in query:
            return query["q"][0]
    return href


def limpar_texto(texto):
    if not texto:
        return texto

    # Remove símbolos estranhos no começo da string
    texto = regex.sub(r'^[^\w(]+', '', texto)

    # Remove quebras de linha
    texto = texto.replace("\n", " ").replace("\r", " ")

    # Remove múltiplos espaços
    texto = regex.sub(r'\s+', ' ', texto)

    return texto.strip()

def enriquecer_empresas(empresas):

    with sync_playwright() as p:
        
        context = p.chromium.launch_persistent_context(
                user_data_dir="perfil_google_serp",
                headless=False,
                slow_mo=random.randint(40, 120)
            )
        

        page = context.new_page()

        primeira = True   # 👈 controle

        for empresa in empresas:

            nome_pesquisa = quote_plus(empresa["nome"])
            url = f"https://www.google.com/search?q={nome_pesquisa}"

            print("🔎 Pesquisando:", empresa["nome"])

            page.goto(url, timeout=60000)
            

            if primeira:
                print("👉 Se aparecer CAPTCHA, resolva manualmente.")
                input("Depois pressione ENTER para continuar...")
                primeira = False  # 👈 nunca mais pede

            time.sleep(random.uniform(8, 15))

            texto_pagina = page.content()

            for chave, valor in empresa.items():
                if isinstance(valor, str):
                    empresa[chave] = limpar_texto(valor)
            

            # =====================
            # TELEFONE
            # =====================
            if not empresa.get("telefone"):
                telefones = regex.findall(r"\(?\d{2}\)?\s?\d{4,5}-\d{4}", texto_pagina)
              
                if telefones:
                    empresa["telefone"] = limpar_texto(telefones[0])

            # =====================
            # CNPJ (segunda busca)
            # =====================
            if not empresa.get("cnpj"):
                print("🔎 Buscando CNPJ de:", empresa["nome"])
                nome_cnpj = quote_plus(f"{empresa['nome']} {empresa.get('endereco','')} cnpj")
                url_cnpj = f"https://www.google.com/search?q={nome_cnpj}"
                page.goto(url_cnpj, timeout=60000)
                time.sleep(5)
                texto_visivel = page.inner_text("body")
                import re
                cnpj = regex.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", texto_visivel)
                if not cnpj:
                    cnpj = regex.search(r"\b\d{14}\b", texto_visivel)
                if cnpj:
                    empresa["cnpj"] = cnpj.group()
                    print("✅ CNPJ encontrado:", empresa["cnpj"])
                else:
                    empresa["cnpj"] = ""
                    print("❌ CNPJ não encontrado")

            # =====================
            # INSTAGRAM
            # =====================
            for a in page.query_selector_all("a"):
                    href = a.get_attribute("href")
                    href_limpo = limpar_link_google(href)

                    if href_limpo and "instagram.com" in href_limpo:
                        empresa["instagram"] = href_limpo
                        break

            # =====================
            # SITE
            # =====================
            for a in page.query_selector_all("a"):
                href = a.get_attribute("href")
                if href and href.startswith("http") and "google" not in href:
                    empresa["site"] = href
                    break

        context.close()

    return empresas