import requests
from bs4 import BeautifulSoup
import difflib
import time
import os
import hashlib
import re

# --- CONFIGURATION ---
TARGET_URLS = [
    "https://codec.kyiv.ua/ad0be.html",
    "https://codec.kyiv.ua/ofx.html"
]

STATE_FILE_PREFIX = "memory_"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

# --- HELPER FUNCTIONS ---
def get_safe_filename(url):
    """Creates a safe, unique filename for a URL to use for its memory file."""
    return STATE_FILE_PREFIX + hashlib.sha1(url.encode()).hexdigest() + ".txt"

def get_previous_links(filename):
    if not os.path.exists(filename):
        return []
    with open(filename, 'r', encoding='utf-8') as f:
        return f.read().splitlines()

def update_links_memory(filename, new_links_list):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("\n".join(new_links_list))

def send_telegram_notification(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ERROR: Telegram secrets are not set."); return
    
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    max_length = 4096
    if len(message) > max_length:
        message = message[:max_length - 10] + "\n[...]"

    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        response = requests.post(api_url, json=payload)
        response.raise_for_status()
        print(f"✅ Successfully sent Telegram notification.")
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to send Telegram notification: {e}")

# --- CORE LOGIC with WHITESPACE NORMALIZATION ---
def check_for_changes(url):
    print(f"\n-> Checking: {url}")
    memory_filename = get_safe_filename(url)
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        
        links = soup.find_all('a', href=True)
        
        current_links = []
        for link in links:
            text = link.get_text(strip=True)
            if text:
                normalized_text = re.sub(r'\s+', ' ', text).strip()
                current_links.append(normalized_text)
        current_links = sorted(current_links)

        previous_links = get_previous_links(memory_filename)

        if not previous_links:
            print("  First run for this URL. Saving initial list of links.")
            # THIS IS THE LINE THAT IS NOW CORRECTED
            update_links_memory(memory_filename, current_links)
            send_telegram_notification(f"✅ Now monitoring links on:\n{url}")
            return

        if previous_links != current_links:
            print("  >>> CHANGE DETECTED IN LINKS! <<<")
            
            diff = difflib.unified_diff(
                previous_links, current_links,
                fromfile='Old Links', tofile='New Links', lineterm=''
            )
            
            changes = [line for line in diff if (line.startswith('+') or line.startswith('-')) and not (line.startswith('---') or line.startswith('+++'))]
            
            formatted_changes = '\n'.join(changes[:20])
            message = f"🚨 **Links Updated!** 🚨\n\nPage:\n{url}\n\n*Report:*\n```\n{formatted_changes}\n```"

            send_telegram_notification(message)
            update_links_memory(memory_filename, current_links)
            print("  Updated links in memory file.")
            
        else:
            print("  No changes detected in links.")

    except Exception as e:
        print(f"  An error occurred for {url}: {e}")

# --- MAIN SCRIPT ---
if __name__ == "__main__":
    print("--- Starting Link Change Detector ---")
    for url in TARGET_URLS:
        check_for_changes(url)
        time.sleep(2)
    print("\n--- Detection Cycle Complete ---")
