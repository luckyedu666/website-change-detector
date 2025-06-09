import requests
from bs4 import BeautifulSoup
import difflib
import time
import os

# --- CONFIGURATION ---
# !!! IMPORTANT: Change this URL to the website you want to track !!!
TARGET_URL = "https://www.example.com/software-list"

# !!! OPTIONAL BUT RECOMMENDED !!!
# To avoid alerts from ads or timestamps, find the ID of the specific div
# that contains the list you care about and put it here.
# Example: TARGET_ELEMENT_ID = "software-updates-container"
# If you want to track the whole page, leave this as None.
TARGET_ELEMENT_ID = None

# New memory file
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
    # We truncate the message to avoid hitting Telegram's message length limit
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
    print(f"Checking for updates at: {TARGET_URL}")
    try:
        response = requests.get(TARGET_URL, headers=HEADERS)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")
        
        if TARGET_ELEMENT_ID:
            content_element = soup.find(id=TARGET_ELEMENT_ID)
            if not content_element:
                print(f"Error: Could not find element with ID '{TARGET_ELEMENT_ID}'. Checking whole page instead.")
                current_content = soup.get_text()
            else:
                print(f"Successfully found element with ID '{TARGET_ELEMENT_ID}'.")
                current_content = content_element.get_text()
        else:
            current_content = soup.get_text()
        
        previous_content = get_previous_content()

        if previous_content and previous_content != current_content:
            print("  >>> CHANGE DETECTED! <<<")
            
            diff = difflib.unified_diff(
                previous_content.splitlines(),
                current_content.splitlines(),
                fromfile='Before',
                tofile='After',
                lineterm='',
            )
            
            changes = []
            for line in diff:
                if line.startswith('+') and not line.startswith('+++'):
                    changes.append(line[1:].strip()) # Get added lines
                elif line.startswith('-') and not line.startswith('---'):
                    changes.append(line[1:].strip()) # Get removed lines

            if not changes:
                message = f"🚨 WEBSITE UPDATED 🚨\n\nA minor change (like spacing) was detected on:\n{TARGET_URL}"
            else:
                # We'll show a maximum of 10 changed lines to keep the message clean
                formatted_changes = '\n'.join(changes[:10])
                message = f"🚨 WEBSITE UPDATED 🚨\n\nChanges detected on:\n{TARGET_URL}\n\n*Changes:*\n```\n{formatted_changes}\n```"

            send_telegram_notification(message)
            update_content_memory(current_content)
            print("  Updated content in memory file.")
            
        elif not previous_content:
            print("  First run. Saving initial content to memory.")
            update_content_memory(current_content)
            send_telegram_notification(f"✅ Monitoring started for:\n{TARGET_URL}")
        else:
            print("  No changes detected.")

    except Exception as e:
        print(f"An error occurred: {e}")

# --- MAIN SCRIPT ---
if __name__ == "__main__":
    print("--- Starting Website Change Detector ---")
    check_for_changes()
    print("--- Detection Cycle Complete ---")
