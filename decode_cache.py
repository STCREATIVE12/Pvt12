import sqlite3
import urllib.request
import os
import json

# File URL aur local save path
DB_URL = "https://raw.githubusercontent.com/byte-capsule/FanCode-Hls-Fetcher/refs/heads/main/cache.db"
LOCAL_DB = "cache_temp.db"
OUTPUT_JSON = "decoded_streams.json"

def download_cache(url, dest):
    print("[*] cache.db download ho rahi hai...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response, open(dest, 'wb') as out_file:
        out_file.write(response.read())
    print("[+] Download complete.")

def decode_database(db_path):
    print("[*] Database read ki ja rahi hai...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Cache table se key aur value fetch karna
    cursor.execute("SELECT key, value FROM Cache WHERE value IS NOT NULL")
    rows = cursor.fetchall()

    decoded_data = []

    for row in rows:
        key_raw, val_raw = row[0], row[1]
        
        # Binary data ko string mein decode karna
        key_str = key_raw.decode('utf-8', errors='ignore') if isinstance(key_raw, bytes) else str(key_raw)
        val_str = val_raw.decode('utf-8', errors='ignore') if isinstance(val_raw, bytes) else str(val_raw)

        # Agar value mein URL maujood hai
        if "http" in val_str:
            # Clean URL extract karna
            url_part = val_str[val_str.find("http"):]
            decoded_data.append({
                "key": key_str.strip(),
                "url": url_part.strip()
            })

    conn.close()
    return decoded_data

# Main Execution
if __name__ == "__main__":
    try:
        # 1. Download
        download_cache(DB_URL, LOCAL_DB)

        # 2. Decode
        results = decode_database(LOCAL_DB)

        # 3. Output print karna
        print(f"\n[+] Total {len(results)} stream URLs decode hue:\n")
        for item in results:
            print(f"Key : {item['key']}")
            print(f"URL : {item['url']}\n")

        # 4. JSON file mein save karna
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4)
        print(f"[+] Saara data '{OUTPUT_JSON}' mein save ho gaya.")

    except Exception as e:
        print(f"[-] Error: {e}")

    finally:
        # Temporary DB file delete karna
        if os.path.exists(LOCAL_DB):
            os.remove(LOCAL_DB)
