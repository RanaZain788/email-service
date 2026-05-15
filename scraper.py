import json
import os
import sys
import re
import time
from datetime import datetime

# Playwright use karega kyunki JS render karna hai
from playwright.sync_api import sync_playwright

class TempMailScraper:
    def __init__(self):
        self.base_url = "https://tempmail.ninja"
        self.email = None
        self.page = None
        self.browser = None
        
    def start_browser(self):
        """Headless browser start karega"""
        try:
            self.playwright = sync_playwright().start()
            
            # Headless browser launch karega
            self.browser = self.playwright.chromium.launch(
                headless=True,  # True rakh production mein
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu'
                ]
            )
            
            # Context with realistic viewport
            self.context = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            self.page = self.context.new_page()
            return True
            
        except Exception as e:
            print(f"Browser start error: {e}", file=sys.stderr)
            return False
    
    def get_email(self):
        """TempMail.Ninja se email fetch karega with proper waiting"""
        try:
            print("Opening TempMail.Ninja...", file=sys.stderr)
            
            # Page load karega with timeout
            self.page.goto(self.base_url, wait_until='networkidle', timeout=60000)
            
            # Wait for page to fully load
            print("Waiting for page to load completely...", file=sys.stderr)
            self.page.wait_for_load_state('domcontentloaded')
            self.page.wait_for_load_state('networkidle')
            
            # Additional wait kyunki React app hai
            time.sleep(3)
            
            # Multiple attempts to find email
            max_attempts = 10
            for attempt in range(max_attempts):
                print(f"Attempt {attempt + 1}/{max_attempts} to find email...", file=sys.stderr)
                
                # Try multiple selectors jo tu ne HTML mein diye
                selectors = [
                    'span.main-email',
                    '[class*="main-email"]',
                    '[class*="email"]',
                    'span[class*="email"]',
                    'div[class*="email"]',
                    '[data-v-01643e1e] span',  # Vue component se
                ]
                
                for selector in selectors:
                    try:
                        # Element visible ho raha hai ki nahi
                        self.page.wait_for_selector(selector, timeout=5000)
                        element = self.page.locator(selector).first
                        
                        if element.is_visible():
                            text = element.inner_text().strip()
                            print(f"Found text with selector '{selector}': {text}", file=sys.stderr)
                            
                            # Email validation
                            if re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', text):
                                self.email = text
                                print(f"✅ Valid email found: {self.email}", file=sys.stderr)
                                return {
                                    'email': self.email,
                                    'timestamp': datetime.now().isoformat(),
                                    'status': 'active',
                                    'source': 'tempmail.ninja',
                                    'attempts': attempt + 1
                                }
                    except:
                        continue
                
                # Agar email nahi mila, page reload kar ya wait kar
                if attempt < max_attempts - 1:
                    time.sleep(2)
                    # Try clicking refresh/generate button if exists
                    try:
                        refresh_btn = self.page.locator('button:has-text("refresh"), button:has-text("new"), [class*="refresh"]').first
                        if refresh_btn.is_visible():
                            refresh_btn.click()
                            time.sleep(2)
                    except:
                        pass
            
            # Fallback: JavaScript se email nikaalne ki koshish
            print("Trying JavaScript extraction...", file=sys.stderr)
            js_email = self.page.evaluate('''() => {
                // Nuxt app se data nikaalne ki koshish
                if (window.__NUXT__ && window.__NUXT__.state) {
                    // State mein email dhoondhega
                    const state = window.__NUXT__.state;
                    for (let key in state) {
                        if (typeof state[key] === 'string' && state[key].includes('@')) {
                            return state[key];
                        }
                    }
                }
                // DOM se dhoondhega
                const spans = document.querySelectorAll('span');
                for (let span of spans) {
                    if (span.innerText && span.innerText.includes('@')) {
                        return span.innerText.trim();
                    }
                }
                return null;
            }''')
            
            if js_email and re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', js_email):
                self.email = js_email
                return {
                    'email': self.email,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'active',
                    'source': 'tempmail.ninja',
                    'method': 'javascript'
                }
            
            # Screenshot for debugging
            self.page.screenshot(path='debug_screenshot.png')
            print("Screenshot saved for debugging", file=sys.stderr)
            
            # Page source for debugging
            html_content = self.page.content()
            print(f"Page HTML length: {len(html_content)}", file=sys.stderr)
            
            # Last resort: regex se email nikaalne ki koshish
            emails_found = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', html_content)
            if emails_found:
                # Filter out common false positives
                valid_emails = [e for e in emails_found if not any(x in e.lower() for x in ['example', 'test@', 'user@'])]
                if valid_emails:
                    self.email = valid_emails[0]
                    return {
                        'email': self.email,
                        'timestamp': datetime.now().isoformat(),
                        'status': 'active',
                        'source': 'tempmail.ninja',
                        'method': 'regex_fallback'
                    }
            
            return {
                'error': 'Email not found after all attempts',
                'status': 'failed',
                'timestamp': datetime.now().isoformat(),
                'html_length': len(html_content)
            }
            
        except Exception as e:
            print(f"Error in get_email: {e}", file=sys.stderr)
            return {
                'error': str(e),
                'status': 'failed',
                'timestamp': datetime.now().isoformat()
            }
    
    def check_otp(self, email=None):
        """Inbox check karega OTP ke liye"""
        if not email:
            email = self.email
            
        if not email:
            return {'error': 'No email provided'}
        
        try:
            print(f"Checking inbox for {email}...", file=sys.stderr)
            
            # Inbox page par jayega
            inbox_url = f"{self.base_url}/inbox/{email}"
            self.page.goto(inbox_url, wait_until='networkidle', timeout=30000)
            
            # Wait for messages to load
            time.sleep(3)
            
            # Messages dhoondhega
            messages = self.page.evaluate('''() => {
                const msgs = [];
                const rows = document.querySelectorAll('[class*="message"], [class*="email-row"], tr');
                rows.forEach(row => {
                    const subject = row.querySelector('[class*="subject"], td:nth-child(3)')?.innerText || '';
                    const from = row.querySelector('[class*="from"], td:nth-child(2)')?.innerText || '';
                    const body = row.innerText || '';
                    msgs.push({subject, from, body});
                });
                return msgs;
            }''')
            
            print(f"Found {len(messages)} messages", file=sys.stderr)
            
            # OTP check karega
            for msg in messages:
                full_text = f"{msg.get('subject', '')} {msg.get('body', '')}"
                
                # OTP patterns
                patterns = [
                    r'\b\d{4,8}\b',
                    r'(?:otp|code|verify|confirmation)[:\s]+(\d{4,8})',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, full_text, re.IGNORECASE)
                    if match:
                        otp = match.group(1) if match.groups() else match.group(0)
                        return {
                            'otp_found': True,
                            'otp': otp,
                            'sender': msg.get('from', ''),
                            'subject': msg.get('subject', ''),
                            'timestamp': datetime.now().isoformat()
                        }
            
            return {
                'otp_found': False,
                'messages_count': len(messages),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'otp_found': False,
                'error': str(e)
            }
    
    def close(self):
        """Browser close karega"""
        try:
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except:
            pass

def save_to_firebase(data):
    """Firebase mein data save karega"""
    try:
        import firebase_admin
        from firebase_admin import credentials, db
        
        firebase_url = os.getenv('FIREBASE_URL')
        firebase_token = os.getenv('FIREBASE_TOKEN')
        
        if not firebase_url or not firebase_token:
            print("Firebase credentials not found, saving locally", file=sys.stderr)
            with open('email_result.json', 'w') as f:
                json.dump(data, f, indent=2)
            return True
        
        # Parse token
        if isinstance(firebase_token, str):
            import json as json_mod
            cred_info = json_mod.loads(firebase_token)
        else:
            cred_info = firebase_token
        
        # Initialize
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_info)
            firebase_admin.initialize_app(cred, {
                'databaseURL': firebase_url
            })
        
        ref = db.reference('/emails')
        new_ref = ref.push(data)
        print(f"Saved to Firebase with key: {new_ref.key}", file=sys.stderr)
        return True
        
    except Exception as e:
        print(f"Firebase save error: {e}", file=sys.stderr)
        # Fallback: local save
        with open('email_result.json', 'w') as f:
            json.dump(data, f, indent=2)
        return False

def main():
    action = os.getenv('GITHUB_EVENT_INPUTS_ACTION', 'create_email')
    
    scraper = TempMailScraper()
    
    if not scraper.start_browser():
        print(json.dumps({
            'error': 'Failed to start browser',
            'status': 'failed'
        }))
        sys.exit(1)
    
    try:
        if action == 'check_otp':
            result = scraper.check_otp()
        else:
            # Default: create email
            result = scraper.get_email()
            
            # Save to Firebase
            if result.get('status') == 'active':
                save_to_firebase(result)
        
        print(json.dumps(result, indent=2))
        
    finally:
        scraper.close()

if __name__ == "__main__":
    main()
