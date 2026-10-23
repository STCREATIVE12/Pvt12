import os
import json
import base64
import requests
from datetime import datetime, timezone, timedelta
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

# Firebase Config
FIREBASE_CONFIG = {
    "projectNumber": os.getenv("FIREBASE_PROJECT_NUMBER", "459539398637"),
    "appId": os.getenv("FIREBASE_APP_ID", "1:459539398637:android:96270124df48971af131e4"),
    "apiKey": os.getenv("FIREBASE_API_KEY", "AIzaSyBIfjXqlm2QLLctnTUQUNK9j9Kf2ybS7yw"),
    "packageName": os.getenv("PACKAGE_NAME", "com.livxow.tv")
}

DEFAULT_BASE_URLS = [
    "https://sohaidoegeve2.shop/",
    "https://welalagaa.site/"
]

# LivXow Crypto Constants
AES_KEY = os.getenv("AES_KEY", "M8mkKlNL75K4nl15").encode('utf-8')
AES_IV = os.getenv("AES_IV", "kN7m5Kl1pN5nk4xK").encode('utf-8')

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
        substituted = decrypt_substitution(raw)
        padding = (4 - (len(substituted) % 4)) % 4
        padded = substituted + "=" * padding
        decoded_bytes = base64.b64decode(padded)
        
        cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
        decrypted_bytes = unpad(cipher.decrypt(decoded_bytes), AES.block_size)
        
        text = decrypted_bytes.decode('utf-8', errors='ignore').strip()
        return text
    except Exception as e:
        print(f"[-] Decryption error: {e}")
        return raw

def convert_to_ist_formatted(time_val):
    """UTC time string ko IST (+0530) format me convert karta hai"""
    if not time_val:
        return time_val
    try:
        time_str = str(time_val).strip()
        # Alag-alag formats ko parse karne ki koshish
        formats = (
            "%Y/%m/%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S %z",
            "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"
        )
        
        for fmt in formats:
            try:
                if '%z' in fmt or '+' in time_str or 'Z' in time_str:
                    clean_str = time_str.replace('Z', '+0000')
                    dt = datetime.strptime(clean_str, fmt if '%z' in fmt else "%Y/%m/%d %H:%M:%S %z")
                else:
                    dt = datetime.strptime(time_str, fmt)
                    dt = dt.replace(tzinfo=timezone.utc)
                
                # Convert to IST (+5:30)
                ist_tz = timezone(timedelta(hours=5, minutes=30))
                dt_ist = dt.astimezone(ist_tz)
                return dt_ist.strftime("%Y/%m/%d %H:%M:%S +0530")
            except ValueError:
                continue
        return time_str
    except Exception:
        return time_val

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
    print("[+] Starting Enhanced LivXow Live Events Extractor with IST Start/End Time conversion...")
    
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

    print(f"[+] Found {len(event_list)} events. Converting StartTime/endTime to IST & resolving streams...")
    
    processed_events = []
    for ev in event_list:
        # StartTime, endTime ya kisi bhi time field ko IST me convert karna
        for key in list(ev.keys()):
            if any(k in key.lower() for k in ["start", "end", "time", "date"]):
                if isinstance(ev[key], str) and len(ev[key]) > 5:
                    ev[key] = convert_to_ist_formatted(ev[key])
        
        # Resolve stream links
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
    
    output_file = "livxow_live_events.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(master_data, f, indent=4, ensure_ascii=False)
        
    print(f"[+] Success! Saved with IST converted StartTime/endTime to {output_file}")

if __name__ == "__main__":
    main()
    
