
import json
import sqlite3
import urllib.request
import re
import os
from datetime import datetime

CACHE_DB_URL = "https://raw.githubusercontent.com/byte-capsule/FanCode-Hls-Fetcher/refs/heads/main/cache.db"
LOCAL_DB = "cache_temp.db"
OUTPUT_JSON = "fancode_simple_matches.json"

TELEGRAM_LINK = "https://t.me/+rQTz5VL8CRpjNTZl"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://fancode.com/"
}

def download_cache(url, dest):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp, open(dest, 'wb') as f:
        f.write(resp.read())

def get_live_match_ids_from_cache(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT value FROM Cache WHERE value IS NOT NULL")
    rows = cur.fetchall()
    
    live_ids = set()
    for row in rows:
        val_str = row[0].decode('utf-8', errors='ignore') if isinstance(row[0], bytes) else str(row[0])
        # Stream URL se match ID match karna
        match_id_search = re.search(r'/(?:primary/|mumbai/)?(\d{5,8})_', val_str)
        if match_id_search:
            live_ids.add(int(match_id_search.group(1)))
    conn.close()
    return live_ids

def fetch_fancode_api():
    # Official endpoint for live & upcoming schedule
    api_url = "https://api.fancode.com/v1/home/matches"
    try:
        req = urllib.request.Request(api_url, headers=HEADERS)
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"[-] API Error: {e}")
        return None

def format_start_time(iso_or_epoch):
    try:
        if isinstance(iso_or_epoch, (int, float)):
            dt = datetime.fromtimestamp(iso_or_epoch / 1000 if iso_or_epoch > 1e11 else iso_or_epoch)
        else:
            dt = datetime.fromisoformat(iso_or_epoch.replace("Z", "+00:00"))
        return dt.strftime("%I:%M:%S %p %d-%m-%Y")
    except Exception:
        return datetime.now().strftime("%I:%M:%S %p %d-%m-%Y")

def main():
    print("[*] Downloading latest cache.db...")
    try:
        download_cache(CACHE_DB_URL, LOCAL_DB)
        cached_live_ids = get_live_match_ids_from_cache(LOCAL_DB)
        print(f"[+] Found {len(cached_live_ids)} active match IDs in cache.")
    except Exception as e:
        print(f"[-] Cache download failed: {e}")
        cached_live_ids = set()
    finally:
        if os.path.exists(LOCAL_DB):
            os.remove(LOCAL_DB)

    print("[*] Fetching FanCode API matches...")
    api_data = fetch_fancode_api()

    now = datetime.now()
    output = {
        "name": "Fancode Live Matches Data in Json",
        "telegram": TELEGRAM_LINK,
        "last update time": now.strftime("%I:%M:%S %p %d-%m-%Y"),
        "matches": []
    }

    # API response parsing (fallback to cache IDs if API is empty/blocked)
    if api_data and "matches" in api_data:
        raw_matches = api_data.get("matches", [])
        for m in raw_matches:
            mid = m.get("id") or m.get("match_id")
            category = m.get("sport_name") or m.get("category", "Cricket")
            t1 = m.get("team_1_name") or m.get("team1", "Team 1")
            t2 = m.get("team_2_name") or m.get("team2", "Team 2")
            event = m.get("tour_name") or m.get("tournament", "League")
            match_name = f"{t1} vs {t2}"
            title = f"{match_name} ({event})"
            
            # Status determination
            status = "UPCOMING"
            if mid in cached_live_ids or m.get("status") in ["LIVE", "STARTED"]:
                status = "LIVE"
            elif m.get("status") in ["PAUSED", "INNINGS_BREAK"]:
                status = "PAUSED"

            src_img = m.get("src") or m.get("image") or f"https://images.fancode.com/aig/match/v1/{mid}_CASACARDS_APP.png"
            start_time = format_start_time(m.get("startTime") or m.get("start_time"))

            output["matches"].append({
                "event_category": category,
                "match_id": int(mid),
                "title": title,
                "match_name": match_name,
                "event_name": event,
                "src": src_img,
                "team_1": t1,
                "team_2": t2,
                "status": status,
                "startTime": start_time
            })
    else:
        # Fallback using decrypted IDs from cache if API is unavailable
        print("[!] Generating from cached IDs...")
        for mid in cached_live_ids:
            output["matches"].append({
                "event_category": "Cricket",
                "match_id": mid,
                "title": f"Live Match {mid}",
                "match_name": f"Team A vs Team B",
                "event_name": "FanCode Live Series",
                "src": f"https://images.fancode.com/aig/match/v1/{mid}_CASACARDS_APP.png",
                "team_1": "Team A",
                "team_2": "Team B",
                "status": "LIVE",
                "startTime": now.strftime("%I:%M:%S %p %d-%m-%Y")
            })

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    print(f"[+] Done! Processed {len(output['matches'])} matches saved to '{OUTPUT_JSON}'.")

if __name__ == "__main__":
    main()
    
