import json
import os
import sys
import re
import time
import random
from datetime import datetime
import urllib.request
import urllib.error

# Selenium with proxy support
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

class TempMailScraper:
    def __init__(self):
        self.base_url = "https://tempmail.ninja"
        self.email = None
        self.driver = None
        
        # 🔥 PROXY CONFIGURATION - YEH ENV VARIABLES SE AAYEGA
        self.proxy_list = self._load_proxies()
        self.current_proxy = None
        
    def _load_proxies(self):
        """Proxies load karega environment se"""
        proxies = []
        
        # Format: http://user:pass@host:port ya http://host:port
        proxy_env = os.getenv('PROXIES', '')
        
        if proxy_env:
            # Comma separated proxies
            proxies = [p.strip() for p in proxy_env.split(',') if p.strip()]
        
        # Agar single proxy hai to bhi handle karega
        http_proxy = os.getenv('HTTP_PROXY', '')
        https_proxy = os.getenv('HTTPS_PROXY', '')
        socks_proxy = os.getenv('SOCKS5_PROXY', '')
        
        if http_proxy and http_proxy not in proxies:
            proxies.append(http_proxy)
        if https_proxy and https_proxy not in proxies:
            proxies.append(https_proxy)
        if socks_proxy and socks_proxy not in proxies:
            proxies.append(socks_proxy)
        
        print(f"Loaded {len(proxies)} proxies", file=sys.stderr)
        return proxies
    
    def _get_random_proxy(self):
        """Random proxy select karega"""
        if not self.proxy_list:
            return None
        return random.choice(self.proxy_list)
    
    def _setup_proxy(self, chrome_options, proxy_url):
        """Chrome mein proxy configure karega"""
        if not proxy_url:
            return
        
        self.current_proxy = proxy_url
        print(f"Using proxy: {proxy_url}", file=sys.stderr)
        
        # Proxy format handle karega
        if proxy_url.startswith('socks5://'):
            # SOCKS5 proxy
            chrome_options.add_argument(f'--proxy-server={proxy_url}')
            # SOCKS5 ke liye alag handling
            chrome_options.add_argument(f'--socks-proxy={proxy_url.replace("socks5://", "")}')
        else:
            # HTTP/HTTPS proxy
            chrome_options.add_argument(f'--proxy-server={proxy_url}')
        
        # Proxy authentication ke liye
        if '@' in proxy_url:
            # user:pass@host:port format
            # Chrome mein extension ki zaroorat padti hai auth ke liye
            pass  # Agar auth wala proxy hai to neeche extension use karega
    
    def _create_proxy_auth_extension(self, proxy):
        """Proxy authentication ke liye Chrome extension"""
        if not proxy or '@' not in proxy:
            return None
        
        # Parse proxy URL
        # Format: http://user:pass@host:port
        match = re.match(r'^(?:http|https|socks5)://([^:]+):([^@]+)@(.+):(\d+)$', proxy)
        if not match:
            return None
        
        user, pwd, host, port = match.groups()
        
        # Manifest JSON
        manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Chrome Proxy",
            "permissions": [
                "proxy",
                "tabs",
                "unlimitedStorage",
                "storage",
                "<all_urls>",
                "webRequest",
                "webRequestBlocking"
            ],
            "background": {
                "scripts": ["background.js"]
            },
            "minimum_chrome_version":"22.0.0"
        }
        """
        
        # Background JS
        background_js = """
        var config = {
                mode: "fixed_servers",
                rules: {
                  singleProxy: {
                    scheme: "http",
                    host: "%s",
                    port: parseInt(%s)
                  },
                  bypassList: ["localhost"]
                }
              };

        chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});

        function callbackFn(details) {
            return {
                authCredentials: {
                    username: "%s",
                    password: "%s"
                }
            };
        }

        chrome.webRequest.onAuthRequired.addListener(
                    callbackFn,
                    {urls: ["<all_urls>"]},
                    ['blocking']
        );
        """ % (host, port, user, pwd)
        
        # Extension create karega
        import zipfile
        pluginfile = 'proxy_auth_plugin.zip'
        
        with zipfile.ZipFile(pluginfile, 'w') as zp:
            zp.writestr("manifest.json", manifest_json)
            zp.writestr("background.js", background_js)
        
        return pluginfile
    
    def start_browser(self):
        """Proxy ke saath headless Chrome start karega"""
        try:
            chrome_options = Options()
            
            # Headless mode
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--window-size=1920,1080')
            
            # Stealth options
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-images')
            chrome_options.add_argument('--disable-javascript')  # JS disable mat karna, email JS se aata hai
            
            # Realistic user agent
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Disable automation flags
            chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # 🔥 PROXY SETUP
            proxy = self._get_random_proxy()
            if proxy:
                # Agar proxy mein auth hai to extension use karega
                if '@' in proxy:
                    extension = self._create_proxy_auth_extension(proxy)
                    if extension:
                        chrome_options.add_extension(extension)
                else:
                    self._setup_proxy(chrome_options, proxy)
            else:
                print("WARNING: No proxy configured! Cloudflare may block.", file=sys.stderr)
            
            # Chrome start karega
            self.driver = webdriver.Chrome(options=chrome_options)
            
            # Stealth mode execute karega
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });
                    window.chrome = { runtime: {} };
                '''
            })
            
            return True
            
        except Exception as e:
            print(f"Browser start error: {e}", file=sys.stderr)
            return False
    
    def get_email(self):
        """TempMail.Ninja se email fetch karega with retry"""
        max_retries = 3
        
        for retry in range(max_retries):
            try:
                print(f"\n🚀 Attempt {retry + 1}/{max_retries}", file=sys.stderr)
                
                # Fresh browser start har retry pe
                if self.driver:
                    self.driver.quit()
                
                if not self.start_browser():
                    continue
                
                print("Opening TempMail.Ninja...", file=sys.stderr)
                self.driver.get(self.base_url)
                
                # Wait for Cloudflare challenge solve hone de
                print("Waiting for Cloudflare/JS challenge...", file=sys.stderr)
                time.sleep(8)  # Important: Cloudflare solve hone tak wait
                
                # Check agar block hua hai
                if "blocked" in self.driver.page_source.lower() or "cloudflare" in self.driver.page_source.lower():
                    print("⚠️ Cloudflare block detected, trying next proxy...", file=sys.stderr)
                    if retry < max_retries - 1:
                        continue
                    else:
                        return {
                            'error': 'Cloudflare blocked all proxies',
                            'status': 'failed',
                            'timestamp': datetime.now().isoformat()
                        }
                
                # Page load wait
                time.sleep(3)
                
                # Email find karega
                result = self._extract_email()
                if result.get('status') == 'active':
                    return result
                
                # Agar nahi mila to retry
                if retry < max_retries - 1:
                    print("Email not found, retrying with new proxy...", file=sys.stderr)
                    time.sleep(2)
                
            except Exception as e:
                print(f"Error in attempt {retry + 1}: {e}", file=sys.stderr)
                if retry < max_retries - 1:
                    time.sleep(3)
        
        # All retries failed
        return {
            'error': 'Failed after all retries',
            'status': 'failed',
            'timestamp': datetime.now().isoformat()
        }
    
    def _extract_email(self):
        """Email extract karega page se"""
        try:
            # Multiple selectors try karega
            selectors = [
                'span.main-email',
                '[class*="main-email"]',
                '[class*="email"]',
                'span[class*="email"]',
                'div[class*="email"]',
            ]
            
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', text):
                            self.email = text
                            print(f"✅ Email found: {self.email}", file=sys.stderr)
                            return {
                                'email': self.email,
                                'timestamp': datetime.now().isoformat(),
                                'status': 'active',
                                'source': 'tempmail.ninja',
                                'proxy_used': self.current_proxy
                            }
                except:
                    continue
            
            # JavaScript se try karega
            print("Trying JavaScript extraction...", file=sys.stderr)
            js_result = self.driver.execute_script('''
                if (window.__NUXT__ && window.__NUXT__.state) {
                    const state = window.__NUXT__.state;
                    for (let key in state) {
                        if (typeof state[key] === 'string' && state[key].includes('@')) {
                            return state[key];
                        }
                    }
                }
                const spans = document.querySelectorAll('span');
                for (let s of spans) {
                    if (s.innerText && s.innerText.includes('@')) return s.innerText.trim();
                }
                return null;
            ''')
            
            if js_result and re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', js_result):
                self.email = js_result
                return {
                    'email': self.email,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'active',
                    'source': 'tempmail.ninja',
                    'method': 'javascript',
                    'proxy_used': self.current_proxy
                }
            
            # Screenshot for debug
            self.driver.save_screenshot('debug_screenshot.png')
            
            return {
                'error': 'Email not found on page',
                'status': 'failed',
                'timestamp': datetime.now().isoformat(),
                'page_title': self.driver.title
            }
            
        except Exception as e:
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
            inbox_url = f"{self.base_url}/inbox/{email}"
            self.driver.get(inbox_url)
            time.sleep(5)
            
            # Messages find karega
            messages = self.driver.find_elements(By.CSS_SELECTOR, '[class*="message"], tr')
            
            for msg in messages:
                try:
                    text = msg.text
                    
                    # OTP patterns
                    patterns = [
                        r'\b\d{4,8}\b',
                        r'(?:otp|code|verify|confirmation)[:\s]+(\d{4,8})',
                    ]
                    
                    for pattern in patterns:
                        match = re.search(pattern, text, re.IGNORECASE)
                        if match:
                            otp = match.group(1) if match.groups() else match.group(0)
                            return {
                                'otp_found': True,
                                'otp': otp,
                                'timestamp': datetime.now().isoformat()
                            }
                except:
                    continue
            
            return {
                'otp_found': False,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'otp_found': False,
                'error': str(e)
            }
    
    def close(self):
        """Browser close"""
        try:
            if self.driver:
                self.driver.quit()
        except:
            pass

def save_to_firebase(data):
    """Firebase mein save karega"""
    try:
        import firebase_admin
        from firebase_admin import credentials, db
        
        firebase_url = os.getenv('FIREBASE_URL')
        firebase_token = os.getenv('FIREBASE_TOKEN')
        
        if not firebase_url or not firebase_token:
            with open('email_result.json', 'w') as f:
                json.dump(data, f, indent=2)
            return True
        
        if isinstance(firebase_token, str):
            cred_info = json.loads(firebase_token)
        else:
            cred_info = firebase_token
        
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_info)
            firebase_admin.initialize_app(cred, {'databaseURL': firebase_url})
        
        ref = db.reference('/emails')
        ref.push(data)
        return True
        
    except Exception as e:
        print(f"Firebase error: {e}", file=sys.stderr)
        with open('email_result.json', 'w') as f:
            json.dump(data, f, indent=2)
        return False

def main():
    action = os.getenv('GITHUB_EVENT_INPUTS_ACTION', 'create_email')
    
    scraper = TempMailScraper()
    
    try:
        if action == 'check_otp':
            result = scraper.check_otp()
        else:
            result = scraper.get_email()
            if result.get('status') == 'active':
                save_to_firebase(result)
        
        print(json.dumps(result, indent=2))
        
    finally:
        scraper.close()

if __name__ == "__main__":
    main()
