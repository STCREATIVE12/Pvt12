import os
import json
import base64
from datetime import datetime
import requests
from Crypto.Cipher import AES

# Firebase Config & Base URLs from PlayZTV Plugin
FIREBASE_CONFIG = {
    "packageName": "com.playz.tv",
    "apiKey": "AIzaSyDKRqLlbaZBIpHzLBiQTUrJqr3gN-nDWWc",
    "appId": "1:516859456626:android:12a75869902c4f8a6826eb",
    "projectNumber": "516859456626",
    "sdkVersion": "22.1.0",
    "appVersion": "2.1",
    "appBuild": "4"
}

DEFAULT_BASE_URLS = [
    "https://tourniquest.site",
    "https://adsflw.xyz"
]

# PlayZTV Decryption Keys & IVs
PLAYZ_NATIVE_KEY = bytes([99, 122, 49, 52, 82, 83, 116, 107, 78, 48, 49, 80, 86, 69, 53, 119])
PLAYZ_NATIVE_IV = bytes([87, 84, 108, 69, 118, 99, 107, 100, 50, 85, 82, 52, 49, 115, 100, 107])
PLAYZ_PRIMARY_KEY = bytes([98, 47, 49, 106, 109, 108, 53, 110, 107, 52, 120, 53, 107, 55, 112, 78])
PLAYZ_PRIMARY_IV = bytes([49, 52, 110, 77, 107, 56, 109, 78, 53, 75, 108, 53, 75, 76, 55, 108])
PLAYZ_FALLBACK_KEY = bytes([109, 53, 75, 108, 53, 110, 107, 52, 120, 75, 49, 107, 78, 55, 112, 78])
PLAYZ_FALLBACK_IV = bytes([107, 53, 75, 52, 110, 77, 56, 109, 75, 108, 78, 76, 55, 108, 49, 53])

PLAYZ_SUBSTITUTION_FROM = "aAbBcCdDeEfFgGhHiIjJkKlLmMnNoOpPqQrRsStTuUvVwWxXyYzZ"
PLAYZ_SUBSTITUTION_TO = "fFgGjJkKaApPbBmMoOzZeEnNcCdDrRqQtTvVuUxXhHiIwWyYlLsS"
PLAYZ_SUBSTITUTION_REVERSE = {PLAYZ_SUBSTITUTION_TO[i]: PLAYZ_SUBSTITUTION_FROM[i] for i in range(len(PLAYZ_SUBSTITUTION_TO))}

OUTPUT_JSON = "live-events.json"

def aes_cbc_decrypt(ciphertext, key, iv):
    try:
        cipher = AES.new(key, AES.MODE_CBC, iv)
        pt = cipher.decrypt(ciphertext)
        pad = pt[-1]
        if 0 < pad <= 16:
            pt = pt[:-pad]
        return pt.decode('utf-8', errors='ignore').strip()
    except Exception:
        return ""

def swap_adjacent_pairs(b_arr):
    out = bytearray(b_arr)
    for i in range(0, len(out) - 1, 2):
        out[i], out[i+1] = out[i+1], out[i]
    return bytes(out)

def decrypt_playz_payload(raw):
    if not raw or not isinstance(raw, str):
        return raw
    raw = raw.strip()
    if not raw:
        return ""
    if raw.startswith("{") or raw.startswith("[") or raw.startswith("<"):
        return raw

    # Strategy 1: Native Decrypt
    try:
        stripped = "".join(raw.split())
        b1 = base64.b64decode(stripped + "===")
        b1_rev = b1[::-1]
        b2 = swap_adjacent_pairs(b1_rev)
        b2_str = "".join([chr(b) for b in b2]).replace(" ", "")
        b3 = base64.b64decode(b2_str + "===")
        pt = aes_cbc_decrypt(b3, PLAYZ_NATIVE_KEY, PLAYZ_NATIVE_IV)
        text = pt.strip()
        if text.startswith("{") or text.startswith("["):
            return text
    except Exception:
        pass

    # Strategy 2: Primary Decrypt
    try:
        stripped = "".join(raw.split())
        restored = "".join([PLAYZ_SUBSTITUTION_REVERSE.get(ch, ch) for ch in stripped])
        b1 = base64.b64decode(restored + "===")
        b1_str = "".join([chr(b) for b in b1])
        ct = base64.b64decode(b1_str + "===")
        pt = aes_cbc_decrypt(ct, PLAYZ_PRIMARY_KEY, PLAYZ_PRIMARY_IV)
        text = pt.strip()
        if text.startswith("{") or text.startswith("["):
            return text
    except Exception:
        pass

    # Strategy 3: Fallback Decrypt
    try:
        stripped = "".join(raw.split())
        ct = base64.b64decode(stripped + "===")
        pt = aes_cbc_decrypt(ct, PLAYZ_FALLBACK_KEY, PLAYZ_FALLBACK_IV)
        text = pt.strip()
        if text.startswith("{") or text.startswith("["):
            return text
    except Exception:
        pass

    return raw

def fetch_remote_base_urls():
    endpoint = f"https://firebaseremoteconfig.googleapis.com/v1/projects/{FIREBASE_CONFIG['projectNumber']}/namespaces/firebase:fetch"
    payload = {
        "appInstanceId": "1234567890abcdef1234567890abcdef",
        "appInstanceIdToken": "",
        "appId": FIREBASE_CONFIG["appId"],
        "countryCode": "US",
        "languageCode": "en-US",
        "platformVersion": "30",
        "timeZone": "UTC",
        "appVersion": FIREBASE_CONFIG["appVersion"],
        "appBuild": FIREBASE_CONFIG["appBuild"],
        "packageName": FIREBASE_CONFIG["packageName"],
        "sdkVersion": FIREBASE_CONFIG["sdkVersion"],
        "analyticsUserProperties": {}
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
        res = requests.post(endpoint, json=payload, headers=headers, timeout=5)
        if res.status_code < 400:
            entries = res.json().get("entries", {})
            api_url = entries.get("api_url")
            if api_url:
                return [api_url.rstrip("/")]
    except Exception:
        pass
    return []

def get_base_urls():
    urls = []
    remote_urls = fetch_remote_base_urls()
    for u in remote_urls + DEFAULT_BASE_URLS:
        if u not in urls:
            urls.append(u)
    return urls

def fetch_playz_json(path):
    headers = {"User-Agent": "Dalvik/2.1.0 (Linux; U; Android 10; SM-A505F)"}
    base_urls = get_base_urls()
    
    for base_url in base_urls:
        url = path if path.startswith("http") else f"{base_url}/{path.lstrip('/')}"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                decrypted = decrypt_playz_payload(res.text)
                try:
                    data = json.loads(decrypted)
                    if data:
                        return data
                except json.JSONDecodeError:
                    if decrypted.startswith("{") or decrypted.startswith("["):
                        return json.loads(decrypted)
        except Exception:
            continue
    return None

def main():
    print("[+] Fetching events from PlayZTV servers...")
    raw_events = fetch_playz_json("events.txt")
    
    if not raw_events or not isinstance(raw_events, list):
        print("[-] Failed to fetch events!")
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump([], f, indent=4)
        return

    formatted_events = []

    for raw_entry in raw_events:
        try:
            event_obj = raw_entry
            if isinstance(raw_entry, str):
                event_obj = json.loads(raw_entry)
            elif isinstance(raw_entry, dict) and "event" in raw_entry:
                event_obj = json.loads(raw_entry["event"]) if isinstance(raw_entry["event"], str) else raw_entry["event"]

            if not isinstance(event_obj, dict) or event_obj.get("visible") is False:
                continue

            info = event_obj.get("eventInfo", event_obj)
            category = info.get("eventCat", event_obj.get("category", "Live Events"))
            event_name = info.get("eventName", event_obj.get("eventName", "Live Event"))
            
            links_path = event_obj.get("links", "")
            streams_list = []

            if links_path:
                slug = links_path.replace(".txt", "")
                links_data = fetch_playz_json(f"channels/{slug}.txt") or fetch_playz_json(f"{slug}.txt") or fetch_playz_json(links_path)
                
                stream_list = []
                if isinstance(links_data, dict):
                    stream_list = links_data.get("streamUrls", []) or links_data.get("links", []) or []
                elif isinstance(links_data, list):
                    stream_list = links_data

                for link_item in stream_list:
                    name = link_item.get("title", link_item.get("name", "Stream"))
                    raw_url = link_item.get("link", "")
                    api_val = link_item.get("api", "")

                    drm_key = ""
                    drm_scheme = ""
                    token_api = ""

                    if isinstance(api_val, dict):
                        token_api = api_val
                    elif isinstance(api_val, str) and api_val.strip():
                        if ":" in api_val and len(api_val.split(":")) == 2:
                            drm_key = api_val
                            drm_scheme = "clearkey"
                        else:
                            token_api = {
                                "api": api_val,
                                "type": "sp",
                                "url": raw_url if raw_url else "Ok"
                            }

                    streams_list.append({
                        "drm_key": drm_key,
                        "drm_scheme": drm_scheme,
                        "link": raw_url if raw_url else "",
                        "name": name,
                        "token_api": token_api
                    })

            formatted_events.append({
                "category": category,
                "event_info": {
                    "end_time": info.get("endTime", info.get("end_date", "")),
                    "event_name": event_name,
                    "start_time": info.get("startTime", event_obj.get("date", "")),
                    "team_a": info.get("teamA", event_obj.get("teamAName", "")),
                    "team_a_flag": info.get("teamAFlag", event_obj.get("teamAFlag", "")),
                    "team_b": info.get("teamB", event_obj.get("teamBName", "")),
                    "team_b_flag": info.get("teamBFlag", event_obj.get("teamBFlag", ""))
                },
                "id": int(event_obj.get("id", 1)),
                "image": str(event_obj.get("image", info.get("eventLogo", "null"))),
                "streams": streams_list,
                "title": str(event_obj.get("title", event_name))
            })
        except Exception as e:
            print(f"[-] Error parsing event entry: {e}")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as out_json:
        json.dump(formatted_events, out_json, indent=4, ensure_ascii=False)

    print(f"[+] Success! Generated exact format {OUTPUT_JSON} with {len(formatted_events)} events.")

if __name__ == "__main__":
    main()
