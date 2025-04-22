import os
import time
import json
import traceback
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

STATE_FILE = "state.json" #make github secret
BOOK_URLS = json.loads(os.environ["BOOK_URLS"])

EMAIL_SENDER = os.environ["EMAIL_SENDER"]
EMAIL_PASSWORD = os.environ["EMAIL_PWD"]
EMAIL_RECEIVER = os.environ["EMAIL_RECEIVER"]
SUPPER_SECRET_URL = os.environ["SUPPER_SECRET_URL"]

def send_email(subject, body):
    """Send an email with the specified subject and body."""
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
            
        print(f"📧 Email sent: {subject}")
    except Exception as e:
        print(f"⚠️ Failed to send email: {e}")

def send_error_email(error_message, stack_trace):
    """Send an email with error details."""
    subject = "Library Script Error Alert"
    body = f"An error occurred in the Library Script:\n\nError: {error_message}\n\nStack Trace:\n{stack_trace}"
    send_email(subject, body)

def send_success_email(action_type, book_title=None):
    """Send an email notification for successful hold or borrow."""
    book_info = f" for '{book_title}'" if book_title else ""
    subject = f"Library Script: Book {action_type} Successful"
    body = f"Good news! The Library Script has successfully {action_type.lower()} {book_info}."
    send_email(subject, body)

def save_login_session(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    print("🔐 Launching login page...")
    page.goto(f"{SUPPER_SECRET_URL}") #make github secret

    print("🕹️ Please log into your account manually in the browser.")
    input("✅ Press ENTER after you're logged in and see your home page...")

    print("💾 Saving login session to state.json...")
    context.storage_state(path=STATE_FILE)

    browser.close()

def check_and_place_hold(playwright, book_url):
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context(storage_state=STATE_FILE)
    page = context.new_page()

    print(f"🌐 Navigating to book page: {book_url}")
    page.goto(book_url, wait_until="networkidle")
    page.wait_for_timeout(10000)  # Give time for content to load
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(5000)

    book_title = "Unknown Book"
    try:
        title_element = page.locator(".screen-title-circ-title").first
        if title_element.is_visible():
            book_title = title_element.text_content().strip()
            print(f"📖 Book title: {book_title}")
    except Exception as e:
            print(f"⚠️ Error getting book title: {e}")

    try:
        goToShelfElement = page.locator('div.circ-option.circ-exit-option button span[role="text"]:has-text("Go To Shelf")')
        
        if goToShelfElement.is_visible():
            print("📚 'Go To Shelf' is present — book already in your library. Skipping.")
            return False

        placeHoldbutton = page.get_by_role("button", name="Place Hold")
        borrowButton = page.get_by_role("button", name="Borrow")
        if placeHoldbutton.is_visible():
            print("📚 'Place Hold' is available — clicking...")
            placeHoldbutton.click()
            page.wait_for_timeout(2000)
            print("✅ Hold placed!")
            send_success_email("Put a Hold on", book_title)
            return True
        elif borrowButton.is_visible():
            print("📚 'Borrow' is available — clicking...")
            borrowButton.click()
            page.wait_for_timeout(2000)
            print("✅ Borrow placed!")
            send_success_email("Borrowed", book_title)
            return True
        else:
            print("❌ 'Place Hold' or 'Borrow' button not visible — book not available.")
            return False
    except Exception as e:
        error_message = str(e)
        stack_trace = traceback.format_exc()
        print(f"⚠️ Error while processing book: {error_message}")
        send_error_email(error_message, stack_trace)
        return False
    finally:
        browser.close()

def process_all_books(playwright):
    """Process all books in the BOOK_URLS list."""
    results = []
    for index, book_url in enumerate(BOOK_URLS):
        print(f"\n📚 Processing book {index+1} of {len(BOOK_URLS)}...")
        success = check_and_place_hold(playwright, book_url)
        results.append(success)
        
        # Wait a bit between requests to avoid overloading the server
        if index < len(BOOK_URLS) - 1:
            time.sleep(25)
    
    # Summary of results
    successes = results.count(True)
    print(f"\n✅ Summary: Successfully processed {successes} out of {len(BOOK_URLS)} books")
    return successes

def main():
    try:
        with sync_playwright() as p:
            if not os.path.exists(STATE_FILE):
                save_login_session(p)

            process_all_books(p)
    except Exception as e:
        error_message = str(e)
        stack_trace = traceback.format_exc()
        print(f"❌ Error in main execution: {error_message}")
        print(f"Stack trace:\n{stack_trace}")
        send_error_email(error_message, stack_trace)

if __name__ == "__main__":
    main()
