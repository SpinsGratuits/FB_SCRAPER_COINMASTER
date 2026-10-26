import json
import os
import re
from datetime import datetime, timedelta
import cloudscraper
from bs4 import BeautifulSoup

# --- 1. CONFIGURATION ---
filename = "scrapcoinmaster.json"

now = datetime.now()
date_now_str = now.strftime("%d/%m/%Y @ %H:%M")
heure_actuelle_str = now.strftime("%H:%M")
limite_conservation = now - timedelta(days=5)

# Liste d'instances RSSHub de secours pour éviter les blocages de l'instance principale
urls_miroirs = [
    "https://rssforever.com",
    "https://rsshub.app",
    "https://edu.xyz"
]

# --- 2. CHARGEMENT & NETTOYAGE DE L'HISTORIQUE LOCAL ---
anciens_liens = {}
if os.path.exists(filename):
    try:
        with open(filename, mode="r", encoding="utf-8") as json_file:
            data_chargee = json.load(json_file)
            if isinstance(data_chargee, list):
                for item in data_chargee:
                    if "lienurl" in item:
                        try:
                            date_objet = datetime.strptime(item.get("date", ""), "%d/%m/%Y")
                            if date_objet >= limite_conservation:
                                anciens_liens[item["lienurl"]] = item
                        except:
                            anciens_liens[item["lienurl"]] = item
    except Exception as e:
        print(f"[Attention] Impossible de lire l'historique JSON : {e}")

# --- 3. REQUÊTE RÉSEAU AVEC ROTATION ---
scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

posts_data = {}
status_code = 0
instance_fonctionnelle = None

print("[Réseau] Tentative de connexion aux instances de secours...")
for url in urls_miroirs:
    try:
        print(f"[Réseau] Test de l'URL : {url}")
        response = scraper.get(url, timeout=12)
        status_code = response.status_code
        
        if status_code == 200:
            posts_data = response.json()
            # Si l'instance renvoie un JSON valide mais vide (Facebook refuse l'accès), on continue
            if posts_data.get("items"):
                instance_fonctionnelle = url
                print(f"[Succès] Données récupérées via : {url}")
                break
            else:
                print("[Info] L'instance a répondu mais la liste des posts Facebook est vide.")
        else:
            print(f"[Attention] L'instance a renvoyé un code erreur HTTP : {status_code}")
    except Exception as e:
        print(f"[Erreur] Impossible de joindre cette instance : {e}")

# --- 4. PARSING DES POSTS FACEBOOK ---
if instance_fonctionnelle and "items" in posts_data:
    json_data = []
    liens_visites_session = set()
    nouveaux_liens_detectes = 0  
    
    current_date_str = now.strftime("%d/%m/%Y")
    
    # On parcourt les derniers posts publiés sur la page officielle
    for post in posts_data.get("items", []):
        html_content = post.get("content_html", "")
        soup_post = BeautifulSoup(html_content, "html.parser")
        
        # Récupération de la date de publication du post Facebook (Format ISO)
        date_pub_iso = post.get("date_published", "")
        try:
            # Extraction propre de la partie YYYY-MM-DD
            date_claire = date_pub_iso.split("T")[0] 
            date_objet = datetime.strptime(date_claire, "%Y-%m-%d")
            
            if date_objet < limite_conservation:
                continue
            current_date_str = date_objet.strftime("%d/%m/%Y")
        except Exception as e:
            current_date_str = now.strftime("%d/%m/%Y")
        
        # Extraction des liens présents dans le texte du post Facebook
        links = soup_post.find_all("a", href=True)
        for link in links:
            href = link["href"].strip()
            
            # Vos filtres stricts d'exclusion
            if href.startswith("/") or "t.me" in href.lower() or "telegram.me" in href.lower():
                continue
            if any(p in href.lower() for p in ["twitter.com", "facebook.com", "whatsapp", "pinterest", "reddit.com", "instagram.com"]):
                continue
                
            # Les signatures des liens de récompenses distribués par Moon Active
            keywords = ["coinmaster", "static-mat", "t.co", "bit.ly", "moonactive", "getcoinmaster"]
            if any(key in href.lower() for key in keywords):
                
                if href in liens_visites_session:
                    continue
                liens_visites_session.add(href)
                
                type_recompense = "Spins et Coins (Facebook Officiel)"
                
                # --- 5. COMPARAISON ET ATTRIBUTION DES BADGES ---
                if href in anciens_liens:
                    date_premier_scraping_str = anciens_liens[href].get("date_scraping", date_now_str)
                    badge_actuel = ""
                    
                    try:
                        date_premier_scraping = datetime.strptime(date_premier_scraping_str, "%d/%m/%Y @ %H:%M")
                        if now - date_premier_scraping < timedelta(hours=6):
                            badge_actuel = "NEW"
                    except:
                        badge_actuel = anciens_liens[href].get("badge", "")

                    json_data.append({
                        "date_scraping": date_premier_scraping_str, 
                        "date_scraping1": anciens_liens[href].get("date_scraping1", f"{current_date_str} @ {heure_actuelle_str}"),
                        "date": current_date_str,  
                        "heure": anciens_liens[href].get("heure", "00:00"),
                        "recompense": anciens_liens[href].get("recompense", type_recompense), 
                        "lienurl": href,
                        "badge": badge_actuel
                    })
                else:
                    nouveaux_liens_detectes += 1
                    date_scraping1_combinee = f"{current_date_str} @ {heure_actuelle_str}"
                    json_data.append({
                        "date_scraping": date_now_str, 
                        "date_scraping1": date_scraping1_combinee,
                        "date": current_date_str,  
                        "heure": heure_actuelle_str,
                        "recompense": type_recompense, 
                        "lienurl": href,
                        "badge": "NEW" 
                    })

    if not json_data and anciens_liens:
        json_data = list(anciens_liens.values())

    # Tri par date décroissante
    def extraire_cle_parution(item):
        try:
            return datetime.strptime(item.get("date", ""), "%d/%m/%Y").timestamp()
        except:
            return 0

    json_data.sort(key=extraire_cle_parution, reverse=True)

    # Sauvegarde locale du fichier de test
    with open(filename, mode="w", encoding="utf-8") as json_file:
        json.dump(json_data, json_file, indent=4, ensure_ascii=False)
        
    print(f"[Terminé] Fichier Coin Master FB {filename} mis à jour ({len(json_data)} liens valides).")
    print(f"[Mode Test] Nouveaux liens détectés lors de la session : {nouveaux_liens_detectes}")
            
else:
    print("\n[⚠️ ALERTE ÉCHEC] Aucune instance RSSHub n'a réussi à extraire les publications Facebook.")
    print("[Raison] Facebook bloque agressivement les requêtes anonymes en provenance des serveurs cloud.")
