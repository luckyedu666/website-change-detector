import requests
from bs4 import BeautifulSoup
import difflib
import time
import os
import hashlib

# --- CONFIGURATION ---
# This is now a list. Add as many URLs as you want, separated by commas.
TARGET_URLS = [
    "https://codec.kyiv.ua/ad0be.html",
    "https://codec.kyiv.ua/ofx.html"
]

# You can still use this if all pages have a common content area ID.
# If not, leave it as None to check the full page text.
TARGET_ELEMENT_ID = None

# These secrets are securely fetched from GitHub's settings
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

# --- HELPER FUNCTIONS ---
def get_safe_filename(url):
    """Creates a safe, unique filename for a URL to use for its memory file."""
    # We create a short hash of the URL to use as a unique ID
    return hashlib.sha1(url.encode()).hexdigest() + ".txt"

def get_previous_content(filename):
    if not os.path.exists(filename):
        return ""
    with open(filename, 'r', encoding='utf-8') as f:
        return f.read()

def update_content_memory(filename, new_content):
    with open(filename, 'w', encoding='utf-8') as f:
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
def check_url(url, memory_filename):
    """Checks a single URL for changes against its specific memory file."""
    print(f"\nChecking: {url}")
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")
        
        if TARGET_ELEMENT_ID:
            content_element = soup.find(id=TARGET_ELEMENT_ID)
            if not content_element:
                print(f"  Error: Could not find element with ID '{TARGET_ELEMENT_ID}'. Checking whole page.")
                current_content = soup.get_text()
            else:
                print(f"  Successfully found element with ID '{TARGET_ELEMENT_ID}'.")
                current_content = content_element.get_text()
        else:
            current_content = soup.get_text()
        
        previous_content = get_previous_content(memory_filename)

        if previous_content and previous_content != current_content:
            print("  >>> CHANGE DETECTED! <<<")
            
            diff = difflib.unified_diff(
                previous_content.splitlines(), current_content.splitlines(),
                fromfile='Before', tofile='After', lineterm=''
            )
            changes = [line[1:].strip() for line in diff if line.startswith('+') or line.startswith('-') and not (line.startswith('---') or line.startswith('+++'))]

            if not changes:
                message = f"🚨 WEBSITE UPDATED 🚨\n\nA minor change was detected on:\n{url}"
            else:
                formatted_changes = '\n'.join(changes[:10])
                message = f"🚨 WEBSITE UPDATED 🚨\n\nChanges detected on:\n{url}\n\n*Changes:*\n```\n{formatted_changes}\n```"

            send_telegram_notification(message)
            update_content_memory(memory_filename, current_content)
            print("  Updated content in memory file.")
            
        elif not previous_content:
            print("  First run for this URL. Saving initial content to memory.")
            update_content_memory(memory_filename, current_content)
            send_telegram_notification(f"✅ Now monitoring for changes on:\n{url}")
        else:
            print("  No changes detected.")

    except Exception as e:
        print(f"  An error occurred: {e}")

# --- MAIN SCRIPT ---
if __name__ == "__main__":
    print("--- Starting Multi-URL Change Detector ---")
    for url in TARGET_URLS:
        # Create a unique memory file name for each URL
        memory_file = get_safe_filename(url)
        check_url(url, memory_file)
        # Small delay between checking each website to be polite
        time.sleep(2)
    print("\n--- Detection Cycle Complete ---")
