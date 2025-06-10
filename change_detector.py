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
STATE_FILE_PREFIX = "memory_"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

# --- HELPER FUNCTIONS ---
def get_safe_filename(url):
    return STATE_FILE_PREFIX + hashlib.sha1(url.encode()).hexdigest() + ".txt"

def get_previous_links(filename):
    if not os.path.exists(filename):
        return ""
    with open(filename, 'r', encoding='utf-8') as f:
        return f.read()

def update_links_memory(filename, new_links_text):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(new_links_text)

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
        if e.response:
             print(f"Error details: {e.response.text}")

# --- CORE LOGIC with DETAILED DIFF REPORTING ---
def check_for_changes(url):
    print(f"\n-> Checking: {url}")
    memory_filename = get_safe_filename(url)
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        
        # We only look for links inside the main content table to be more specific
        content_table = soup.find('table', {'bgcolor': '#E0E0E0'})
        if not content_table:
            print("  Error: Main content table not found. Checking all links on page.")
            content_table = soup # Fallback to the whole page

        links = content_table.find_all('a', href=True)
        current_links_text = "\n".join(sorted([link.get_text(strip=True) for link in links if link.get_text(strip=True)]))
        
        previous_links_text = get_previous_links(memory_filename)

        if not previous_links_text:
            print("  First run for this URL. Saving initial list of links.")
            update_links_memory(memory_filename, current_links_text)
            send_telegram_notification(f"✅ Now monitoring links on:\n{url}")
            return

        if previous_links_text != current_links_text:
            print("  >>> CHANGE DETECTED IN LINKS! <<<")
            
            # Generate a "diff" report of the changes
            diff = difflib.unified_diff(
                previous_links_text.splitlines(), current_links_text.splitlines(),
                fromfile='Old', tofile='New', lineterm=''
            )
            
            # Format the changes to be clear and readable
            changes = [line for line in diff if (line.startswith('+') or line.startswith('-')) and not (line.startswith('---') or line.startswith('+++'))]
            
            if not changes:
                 message = f"🚨 WEBSITE UPDATED 🚨\n\nA minor (whitespace) change was detected on:\n{url}"
            else:
                formatted_changes = '\n'.join(changes[:20]) # Show max 20 changed lines
                message = f"🚨 **Change Detected on Page:** 🚨\n{url}\n\n*Here is the detailed report:*\n```\n{formatted_changes}\n```"

            send_telegram_notification(message)
            update_links_memory(memory_filename, current_links_text)
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
