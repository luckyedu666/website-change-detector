import requests
from bs4 import BeautifulSoup
import difflib
import time
import os

# --- CONFIGURATION ---
TARGET_URLS = [
    "https://codec.kyiv.ua/ad0be.html",
    "https://codec.kyiv.ua/ofx.html"
]

# This CSS Selector focuses on the main content table, ignoring headers/footers.
TARGET_SELECTOR = 'table[bgcolor="#E0E0E0"]'

# The memory file (no change here)
STATE_FILE = "previous_links.txt"

# These secrets are securely fetched from GitHub's settings
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

# --- HELPER FUNCTIONS ---
def get_previous_links_map():
    if not os.path.exists(STATE_FILE):
        return {}
    link_map = {}
    with open(STATE_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
        if not content: return {}
        # Split the file content by our URL separator
        url_blocks = content.strip().split('|||URL_SEPARATOR|||')
        # Rebuild the dictionary from the flat list
        for block in url_blocks:
            if '|||LINK_SEPARATOR|||' in block:
                url, links_text = block.split('|||LINK_SEPARATOR|||', 1)
                link_map[url.strip()] = links_text.strip()
    return link_map

def update_links_memory(new_link_map):
    memory_string = ""
    for url, links_text in new_link_map.items():
        # Using a more robust separator format
        memory_string += f"{url}|||LINK_SEPARATOR|||{links_text}|||URL_SEPARATOR|||"
        
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        f.write(memory_string)

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

# --- CORE LOGIC with SMART NOTIFICATIONS ---
def check_for_changes():
    print(f"Checking {len(TARGET_URLS)} URLs for link changes...")
    
    previous_links_map = get_previous_links_map()
    all_current_links_map = {}
    any_changes_found = False

    for url in TARGET_URLS:
        print(f"-> Checking: {url}")
        try:
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            
            content_element = soup.select_one(TARGET_SELECTOR)
            if not content_element:
                print(f"  Error: Could not find target element '{TARGET_SELECTOR}'. Skipping URL.")
                continue

            links = content_element.find_all('a', href=True)
            current_links_text = "\n".join(sorted([link.get_text(strip=True) for link in links if link.get_text(strip=True)]))
            all_current_links_map[url] = current_links_text
            
            previous_links_text = previous_links_map.get(url)

            if previous_links_text is None:
                print("  First run for this URL. Saving initial list.")
                any_changes_found = True 
                send_telegram_notification(f"✅ Now monitoring links on:\n{url}")
                continue

            if previous_links_text != current_links_text:
                print("  >>> CHANGE DETECTED IN LINKS! <<<")
                any_changes_found = True
                
                diff = difflib.unified_diff(
                    previous_links_text.splitlines(), current_links_text.splitlines(),
                    fromfile='Old', tofile='New', lineterm=''
                )
                
                added = [line[1:] for line in diff if line.startswith('+') and not line.startswith('+++')]
                
                if not added:
                     # This handles cases where links were only removed or had minor whitespace changes
                     message = f"🚨 LINKS UPDATED 🚨\n\nMinor change or removal detected on:\n{url}"
                else:
                    # Build a smart message
                    formatted_added = '\n'.join(added)
                    message = f"🚨 **New Software/Updates Found!** 🚨\n\nOn page:\n{url}\n\n*Added or Updated:*\n`{formatted_added}`"

                send_telegram_notification(message)
            else:
                print("  No changes detected in links.")

        except Exception as e:
            print(f"  An error occurred for {url}: {e}")
        
        time.sleep(1)

    if any_changes_found:
        print("\nUpdating links memory file...")
        update_links_memory(all_current_links_map)
        print("  Memory file updated.")
    else:
        print("\nNo overall changes. Memory file is up to date.")

# --- MAIN SCRIPT ---
if __name__ == "__main__":
    print("--- Starting Smart Link Detector ---")
    check_for_changes()
    print("--- Detection Cycle Complete ---")
