import json
import os
import re
from datetime import datetime, timedelta
import cloudscraper
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. CONFIGURATION ---
# Utilisation d'une passerelle de scraping Facebook vers JSON résiliente
url = "https://rsshub.app"
filename = "scrapcoinmaster.json"

now = datetime.now()
date_now_str = now.strftime("%d/%m/%Y @ %H:%M")
heure_actuelle_str = now.strftime("%H:%M")
limite_conservation = now - timedelta(days=5)

# --- 1B. INITIALISATION FIREBASE ---
firebase_key_raw = os.environ.get('FIREBASE_KEY')
if not firebase_key_raw:
    raise ValueError("Le secret FIREBASE_KEY est introuvable dans l'environnement.")

if not firebase_admin._apps:
    cred_json = json.loads(firebase_key_raw)
    cred = credentials.Certificate(cred_json)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# --- 2. CHARGEMENT & NETTOYAGE DE L'HISTORIQUE ---
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

# --- 3. REQUÊTE RÉSEAU ---
scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

try:
    response = scraper.get(url, timeout=15)
    status_code = response.status_code
    posts_data = response.json() if status_code == 200 else {}
except Exception as e:
    status_code = 500
    posts_data = {}
    print(f"[Erreur] Connexion impossible à la passerelle Facebook : {e}")

# --- 4. PARSING DES POSTS FACEBOOK ---
if status_code == 200 and "items" in posts_data:
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
            # Nettoyage rudimentaire du fuseau horaire Z pour compatibilité Python
            date_claire = date_pub_iso.split("T")[0] # YYYY-MM-DD
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
    print(f"[Diagnostic] Nouveaux liens Facebook détectés : {nouveaux_liens_detectes}")

    # --- 6. EXPORTATION NOTIFICATION & ENVOI PUSH DIRECT ---
    if nouveaux_liens_detectes > 0:
        try:
            from firebase_admin import messaging
            
            db.collection("notifications").add({
                "title": "🐷 Facebook Coin Reward ! 🎁",
                "body": "Des spins officiels viennent d'être publiés sur Facebook !",
                "nom_du_jeu": "coin_master",
                "created_at": firestore.SERVER_TIMESTAMP
            })
            print("[Firebase] Enregistrement d'historique créé pour Coin Master FB.")

            message = messaging.Message(
                notification=messaging.Notification(
                    title="🐷 Facebook Coin Reward ! 🎁",
                    body="Des spins officiels viennent d'être publiés sur Facebook !"
                ),
                topic="coin_master"
            )
            
            response = messaging.send(message)
            print(f"[Firebase Push] Notification Flash envoyée aux téléphones ! (ID: {response})")
            
        except Exception as e:
            print(f"[Firebase] [Erreur] Échec de l'envoi Push : {e}")
            
else:
    print(f"[Erreur] Échec d'accès réseau ou format JSON Facebook invalide (Code {status_code}).")
