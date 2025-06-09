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

# --- NEW, FOCUSED APPROACH ---
# This is a CSS Selector. It tells the bot to only look inside the
# main content table on the page, ignoring everything else.
TARGET_SELECTOR = 'table[bgcolor="#E0E0E0"]'

# The memory file (no change here)
STATE_FILE = "previous_content.txt"

# These secrets are securely fetched from GitHub's settings
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

# --- HELPER FUNCTIONS ---
def get_previous_content():
    if not os.path.exists(STATE_FILE):
        return ""
    with open(STATE_FILE, 'r', encoding='utf-8') as f:
        return f.read()

def update_content_memory(new_content):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        f.write(new_content)

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

# --- CORE LOGIC ---
def check_for_changes():
    print(f"Checking {len(TARGET_URLS)} URLs for updates...")
    
    # We now store content for each URL in memory to compare
    previous_contents = get_previous_content().split('|||URL_SEPARATOR|||')
    # Create a dictionary for easy lookup
    previous_content_map = dict(zip(previous_contents[::2], previous_contents[1::2]))
    
    all_current_contents = {}
    changes_found = False

    for url in TARGET_URLS:
        print(f"-> Checking: {url}")
        try:
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, "html.parser")
            
            content_element = soup.select_one(TARGET_SELECTOR)
            
            if not content_element:
                print(f"  Error: Could not find target element with selector '{TARGET_SELECTOR}'.")
                # Add a placeholder to avoid breaking the logic
                all_current_contents[url] = "" 
                continue

            current_content = content_element.get_text()
            all_current_contents[url] = current_content
            
            previous_content = previous_content_map.get(url, "")

            if previous_content and previous_content != current_content:
                print("  >>> CHANGE DETECTED! <<<")
                changes_found = True
                
                diff = difflib.unified_diff(
                    previous_content.splitlines(), current_content.splitlines(),
                    fromfile='Before', tofile='After', lineterm=''
                )
                
                changes = [line for line in diff if line.startswith(('+', '-')) and not line.startswith(('---', '+++'))]
                # Filter out lines that only changed by adding/removing a single space at the end
                changes = [line for line in changes if line[1:].strip() != line[1:-1].strip() or len(line) <= 2]


                if not changes:
                    message = f"🚨 WEBSITE UPDATED 🚨\n\nA minor (whitespace) change was detected on:\n{url}"
                else:
                    formatted_changes = '\n'.join(changes[:15]) # Show up to 15 lines of changes
                    message = f"🚨 WEBSITE UPDATED 🚨\n\nChanges detected on:\n{url}\n\n*Changes:*\n```\n{formatted_changes}\n```"

                send_telegram_notification(message)
                
            elif not previous_content:
                print("  First run for this URL. Saving initial content.")
                changes_found = True # Force a save on the first run
                send_telegram_notification(f"✅ Now monitoring for changes on:\n{url}")
            else:
                print("  No changes detected.")

        except Exception as e:
            print(f"  An error occurred for {url}: {e}")
        
        time.sleep(1) # Small delay between requests

    # After checking all URLs, save the new state
    if changes_found:
        print("\nUpdating content memory file...")
        # Rebuild the string to save from the current contents
        # This handles removed URLs correctly
        new_memory_string = ""
        for url in TARGET_URLS:
            if url in all_current_contents:
                new_memory_string += f"{url}|||URL_SEPARATOR|||{all_current_contents[url]}"
        update_content_memory(new_memory_string)
        print("  Memory file updated.")
    else:
        print("\nNo overall changes. Memory file is up to date.")

# --- MAIN SCRIPT ---
if __name__ == "__main__":
    print("--- Starting Website Change Detector ---")
    check_for_changes()
    print("--- Detection Cycle Complete ---")
