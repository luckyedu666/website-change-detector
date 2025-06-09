import requests
from bs4 import BeautifulSoup
import difflib
import time
import os
import hashlib

# --- CONFIGURATION ---
TARGET_URLS = [
    "https://codec.kyiv.ua/ad0be.html",
    "https://codec.kyiv.ua/ofx.html"
]

# This is our new memory file
STATE_FILE = "previous_links.txt"

# These secrets are securely fetched from GitHub's settings
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

# --- HELPER FUNCTIONS ---
def get_previous_links_map():
    """Reads the old link map from our memory file."""
    if not os.path.exists(STATE_FILE):
        return {}
    
    link_map = {}
    with open(STATE_FILE, 'r', encoding='utf-8') as f:
        # Split the file content by our URL separator
        parts = f.read().split('|||URL_SEPARATOR|||')
        # Rebuild the dictionary from the flat list
        for i in range(0, len(parts) - 1, 2):
            url = parts[i]
            links_text = parts[i+1]
            link_map[url] = links_text
    return link_map

def update_links_memory(new_link_map):
    """Saves the new link map to our memory file."""
    # We build a single string to save, with a clear separator
    # This also handles cases where a URL is removed from the list
    memory_string = ""
    for url, links_text in new_link_map.items():
        memory_string += f"{url}|||URL_SEPARATOR|||{links_text}"
        
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

# --- CORE LOGIC BASED ON YOUR IDEA ---
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
            
            # Find all clickable links (<a> tags with an href)
            links = soup.find_all('a', href=True)
            # Get the clean text from each link and join them into one string
            current_links_text = "\n".join([link.get_text(strip=True) for link in links])
            all_current_links_map[url] = current_links_text
            
            previous_links_text = previous_links_map.get(url)

            # If this is the first run for this URL
            if previous_links_text is None:
                print("  First run for this URL. Saving initial list of links.")
                any_changes_found = True 
                send_telegram_notification(f"✅ Now monitoring links on:\n{url}")
                continue

            # Compare the old list of links with the new one
            if previous_links_text != current_links_text:
                print("  >>> CHANGE DETECTED IN LINKS! <<<")
                any_changes_found = True
                
                diff = difflib.unified_diff(
                    previous_links_text.splitlines(), current_links_text.splitlines(),
                    fromfile='Old Links', tofile='New Links', lineterm=''
                )
                
                # Format a clear message showing only added/removed lines
                changes = [line for line in diff if (line.startswith('+') or line.startswith('-')) and not (line.startswith('---') or line.startswith('+++'))]
                
                formatted_changes = '\n'.join(changes[:20]) # Show max 20 changed lines
                message = f"🚨 LINKS UPDATED 🚨\n\nChanges detected on:\n{url}\n\n*Changes:*\n```\n{formatted_changes}\n```"

                send_telegram_notification(message)
            else:
                print("  No changes detected in links.")

        except Exception as e:
            print(f"  An error occurred for {url}: {e}")
        
        time.sleep(1) # Small delay between requests

    # After checking all URLs, save the new state if anything changed
    if any_changes_found:
        print("\nUpdating links memory file...")
        update_links_memory(all_current_links_map)
        print("  Memory file updated.")
    else:
        print("\nNo overall changes. Memory file is up to date.")

# --- MAIN SCRIPT ---
if __name__ == "__main__":
    print("--- Starting Link Change Detector ---")
    check_for_changes()
    print("--- Detection Cycle Complete ---")
