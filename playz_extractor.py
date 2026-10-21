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

def parse_stream_link(raw_link):
    if not raw_link:
        return "", {}
    parts = raw_link.split("|")
    url = parts[0].strip().replace("%2F", "/")
    headers = {}
    for part in parts[1:]:
        eq = part.find("=")
        if eq > 0:
            k = part[:eq].strip()
            v = part[eq+1:].strip()
            headers[k] = v
    return url, headers

def main():
    print("[+] Fetching events from PlayZTV servers...")
    raw_events = fetch_playz_json("events.txt")
    
    if not raw_events or not isinstance(raw_events, list):
        print("[-] Failed to fetch events!")
        # Empty fallback list save kar do taaki git fail na ho
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
            resolved_streams = []
            format_titles = []

            if links_path:
                slug = links_path.replace(".txt", "")
                links_data = fetch_playz_json(f"{slug}.txt") or fetch_playz_json(links_path)
                
                if links_data and isinstance(links_data, list):
                    for link_item in links_data:
                        title = link_item.get("name", "Stream")
                        format_titles.append(title)
                        raw_url = link_item.get("link", "")
                        clean_url, headers = parse_stream_link(raw_url)
                        api_key = link_item.get("api", "")

                        resolved_streams.append({
                            "api": api_key,
                            "link": clean_url if clean_url else raw_url,
                            "publish": 1,
                            "title": title,
                            "type": "1" if api_key else "0"
                        })

            formatted_events.append({
                "cat": category,
                "eventInfo": {
                    "endTime": info.get("endTime", info.get("end_date", "")),
                    "eventCat": category,
                    "eventLogo": info.get("eventLogo", event_obj.get("eventLogo", "")),
                    "eventName": event_name,
                    "eventType": info.get("eventType", ""),
                    "isHot": str(event_obj.get("isHot", "0")),
                    "startTime": info.get("startTime", event_obj.get("date", "")),
                    "teamA": info.get("teamA", event_obj.get("teamAName", "")),
                    "teamAFlag": info.get("teamAFlag", event_obj.get("teamAFlag", "")),
                    "teamB": info.get("teamB", event_obj.get("teamBName", "")),
                    "teamBFlag": info.get("teamBFlag", event_obj.get("teamBFlag", ""))
                },
                "formats": format_titles,
                "id": int(event_obj.get("id", 1)),
                "image": str(event_obj.get("image", event_obj.get("eventLogo", "null"))),
                "isHot": int(event_obj.get("isHot", 0)),
                "position": int(event_obj.get("position", 0)),
                "publish": int(event_obj.get("publish", 1)),
                "resolved_streams": resolved_streams,
                "slug": str(event_obj.get("slug", links_path.replace(".txt", "") if links_path else "slug-item")),
                "title": str(event_obj.get("title", event_name))
            })
        except Exception as e:
            print(f"[-] Error parsing event entry: {e}")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as out_json:
        json.dump(formatted_events, out_json, indent=4, ensure_ascii=False)

    print(f"[+] Success! Generated {OUTPUT_JSON} with {len(formatted_events)} events.")

if __name__ == "__main__":
    main()
