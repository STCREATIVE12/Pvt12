import os
import json
import base64
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

# Firebase Config from LivXowFirebaseFetcher.java
FIREBASE_CONFIG = {
    "projectNumber": "459539398637",
    "appId": "1:459539398637:android:96270124df48971af131e4",
    "apiKey": "AIzaSyBIfjXqlm2QLLctnTUQUNK9j9Kf2ybS7yw",
    "packageName": "com.livxow.tv"
}

DEFAULT_BASE_URLS = [
    "https://sohaidoegeve2.shop/",
    "https://welalagaa.site/"
]

# LivXow Crypto Constants from LivXowCryptoUtils.java
AES_KEY = b"M8mkKlNL75K4nl15"
AES_IV = b"kN7m5Kl1pN5nk4xK"

STANDARD_ALPHABET = "aAbBcCdDeEfFgGhHiIjJkKlLmMnNoOpPqQrRsStTuUvVwWxXyYzZ"
SHUFFLED_ALPHABET = "fFgGjJkKaApPbBmMoOzZeEnNcCdDrRqQtTvVuUxXhHiIwWyYlLsS"

# Build character substitution mapping table
decode_table = {ord(SHUFFLED_ALPHABET[i]): ord(STANDARD_ALPHABET[i]) for i in range(len(SHUFFLED_ALPHABET))}

def decrypt_substitution(s):
    return "".join([chr(decode_table.get(ord(ch), ord(ch))) for ch in s])

def decrypt_livxow_payload(raw):
    raw = raw.strip()
    if not raw:
        return ""
    if raw.startswith("{") or raw.startswith("[") or raw.startswith("<"):
        return raw

    try:
        # Step 1: Character substitution reverse mapping
        substituted = decrypt_substitution(raw)
        
        # Step 2: Base64 padding correction
        padding = (4 - (len(substituted) % 4)) % 4
        padded = substituted + "=" * padding
        
        # Step 3: Base64 decode
        decoded_bytes = base64.b64decode(padded)
        
        # Step 4: AES-CBC Decryption with PKCS7/5 Unpadding
        cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
        decrypted_bytes = unpad(cipher.decrypt(decoded_bytes), AES.block_size)
        
        text = decrypted_bytes.decode('utf-8', errors='ignore').strip()
        return text
    except Exception as e:
        print(f"[-] Decryption error: {e}")
        return raw

def fetch_firebase_base_url():
    endpoint = f"https://firebaseremoteconfig.googleapis.com/v1/projects/{FIREBASE_CONFIG['projectNumber']}/namespaces/firebase:fetch"
    payload = {
        "appVersion": "2.3",
        "timeZone": "Asia/Calcutta",
        "appInstanceIdToken": "",
        "languageCode": "en-IN",
        "appBuild": "5",
        "appInstanceId": "e8oXwurwSlyewCIEp8rdgs",
        "countryCode": "IN",
        "analyticsUserProperties": {},
        "appId": FIREBASE_CONFIG["appId"],
        "platformVersion": "33",
        "sdkVersion": "23.1.0",
        "packageName": FIREBASE_CONFIG["packageName"]
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Android-Package": FIREBASE_CONFIG["packageName"],
        "X-Goog-Api-Key": FIREBASE_CONFIG["apiKey"],
        "X-Google-GFE-Can-Retry": "yes",
        "User-Agent": "okhttp/4.12.0"
    }
    try:
        res = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        if res.status_code < 400:
            entries = res.json().get("entries", {})
            api_url = entries.get("api_url") or entries.get("web_url")
            if api_url:
                cleaned = api_url.rstrip("/") + "/"
                print(f"[+] Discovered dynamic domain from Firebase: {cleaned}")
                return cleaned
    except Exception as e:
        print(f"[-] Firebase fetch failed: {e}")
    return None

def get_active_base_urls():
    urls = []
    dynamic_url = fetch_firebase_base_url()
    if dynamic_url and dynamic_url not in urls:
        urls.append(dynamic_url)
    for u in DEFAULT_BASE_URLS:
        if u not in urls:
            urls.append(u)
    return urls

def fetch_and_decrypt_file(filename):
    headers = {"User-Agent": "okhttp/4.9.2", "Accept": "*/*"}
    base_urls = get_active_base_urls()
    
    for base_url in base_urls:
        url = f"{base_url.rstrip('/')}/{filename.lstrip('/')}"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                decrypted_text = decrypt_livxow_payload(res.text)
                try:
                    data = json.loads(decrypted_text)
                    return data
                except json.JSONDecodeError:
                    return decrypted_text
        except Exception:
            continue
    return None

def main():
    print("[+] Starting Enhanced LivXow Live Events Extractor...")
    
    # 1. Fetch Categories
    categories = fetch_and_decrypt_file("categories.txt")
    
    # 2. Fetch Events List
    events_raw = fetch_and_decrypt_file("events.txt")
    
    event_list = []
    if isinstance(events_raw, list):
        for item in events_raw:
            if isinstance(item, dict) and "event" in item:
                try:
                    ev = json.loads(item["event"])
                    event_list.append(ev)
                except:
                    pass
            elif isinstance(item, dict):
                event_list.append(item)

    print(f"[+] Found {len(event_list)} events. Resolving stream links...")
    
    processed_events = []
    for ev in event_list:
        links_field = ev.get("links")
        slug = None
        if links_field:
            slug = links_field.replace(".txt", "").strip()
        
        streams = []
        if slug:
            stream_data = fetch_and_decrypt_file(f"{slug}.txt")
            if stream_data:
                if isinstance(stream_data, str):
                    try:
                        stream_data = json.loads(stream_data)
                    except:
                        pass
                if isinstance(stream_data, list):
                    for s_item in stream_data:
                        if isinstance(s_item, dict):
                            if "channel" in s_item:
                                try:
                                    streams.append(json.loads(s_item["channel"]))
                                except:
                                    streams.append(s_item["channel"])
                            elif "stream" in s_item:
                                try:
                                    streams.append(json.loads(s_item["stream"]))
                                except:
                                    streams.append(s_item["stream"])
                            else:
                                streams.append(s_item)
                elif isinstance(stream_data, dict):
                    streams.append(stream_data)

        ev["resolved_streams"] = streams
        processed_events.append(ev)

    master_data = {
        "categories": categories if categories else [],
        "events": processed_events
    }
    
    # Output file renamed as requested
    output_file = "livxow_live_events.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(master_data, f, indent=4, ensure_ascii=False)
        
    print(f"[+] Success! Live events JSON saved to {output_file}")

if __name__ == "__main__":
    main()
