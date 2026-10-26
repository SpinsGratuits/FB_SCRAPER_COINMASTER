import time
import json
import os
import requests
from playwright.sync_api import sync_playwright

FB_PAGE_URL = "https://facebook.com/coinmaster/"
JSON_FILE = "scrapcoinmaster.json"

# METTEZ VOTRE WEBHOOK DISCORD ICI SI BESOIN
DISCORD_WEBHOOK_URL = ""

def load_cached_links():
    if not os.path.exists(JSON_FILE):
        return set(), []
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(item["url"] for item in data), data
    except Exception:
        return set(), []

def save_links_to_json(new_links, existing_data):
    # Insère les nouveautés en haut de la liste
    for link in reversed(new_links):
        existing_data.insert(0, {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "url": link
        })
    try:
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=4, ensure_ascii=False)
        print(f"[JSON] {len(new_links)} nouveau(x) lien(s) sauvegardé(s).")
    except Exception as e:
        print(f"Erreur d'écriture JSON : {e}")

def send_discord_notification(link):
    if not DISCORD_WEBHOOK_URL:
        return
    payload = {"content": f"🚨 **Nouveau lien Coin Master (d10xl) !** 🚨\n👉 {link}"}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    except Exception:
        pass

def extraire_liens():
    links_found = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        try:
            page.goto(SEARCH_URL, wait_until="networkidle")
            page.wait_for_timeout(2000)
            
            # Gestion de la popup de consentement de cookies Google si présente
            try:
                if page.locator("button:has-text('Tout accepter')").is_visible():
                    page.click("button:has-text('Tout accepter')")
                    page.wait_for_timeout(1000)
            except Exception:
                pass

            # Récupération du texte brut de la page pour scanner les motifs textuels
            page_text = page.locator("body").inner_text()
            
            # Recherche de tous les formats d'URLs contenant 'd10xl'
            urls = re.findall(r'https://[^\s"\'>]*d10xl[^\s"\'>]*', page_text, re.IGNORECASE)
            
            for u in urls:
                # Nettoyage des ponctuations de fin de chaîne attrapées par la regex
                u_clean = u.rstrip(".,;:!? )]*")
                if u_clean not in links_found:
                    links_found.append(u_clean)
                    
        except Exception as e:
            print(f"Erreur lors du scraping : {e}")
        finally:
            browser.close()
    return links_found

if __name__ == "__main__":
    print("Vérification des liens officiels Coin Master contenant d10xl...")
    cached_urls, full_data = load_cached_links()
    liens_scrapes = extraire_liens()
    
    nouveaux_liens = [l for l in liens_scrapes if l not in cached_urls]
    
    if nouveaux_liens:
        save_links_to_json(nouveaux_liens, full_data)
        for un_lien in nouveaux_liens:
            send_discord_notification(un_lien)
    else:
        print("Aucun nouveau lien contenant d10xl détecté.")
