import requests
from bs4 import BeautifulSoup
import json
import re
import os
import sys
from datetime import datetime
import time

class EmailScraper:
    def __init__(self):
        self.base_url = "https://tempmail.ninja"
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }
        
    def get_temp_email(self):
        """TempMail.Ninja se naya email fetch karega"""
        try:
            print("Fetching email from TempMail.Ninja...", file=sys.stderr)
            
            # Step 1: Homepage se email lega
            response = self.session.get(
                self.base_url, 
                headers=self.headers, 
                timeout=30,
                allow_redirects=True
            )
            
            print(f"Response status: {response.status_code}", file=sys.stderr)
            
            if response.status_code != 200:
                return {
                    'error': f'HTTP {response.status_code}',
                    'status': 'failed',
                    'timestamp': datetime.now().isoformat()
                }
            
            # Step 2: Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Multiple selectors try karega email ke liye
            email_selectors = [
                'span.main-email',
                '[class*="email"]',
                '[class*="mail"]',
                'span[class*="main"]'
            ]
            
            email = None
            
            for selector in email_selectors:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text(strip=True)
                    # Email validation regex
                    if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', text):
                        email = text
                        print(f"Found email with selector: {selector}", file=sys.stderr)
                        break
            
            if not email:
                # Fallback: Pure text mein email dhoondhega
                text_content = soup.get_text()
                emails_found = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text_content)
                if emails_found:
                    email = emails_found[0]
                    print(f"Found email in text: {email}", file=sys.stderr)
            
            if email:
                return {
                    'email': email,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'active',
                    'source': 'tempmail.ninja',
                    'workflow_id': os.getenv('GITHUB_RUN_ID', 'local')
                }
            else:
                return {
                    'error': 'No email found on page',
                    'status': 'failed',
                    'timestamp': datetime.now().isoformat(),
                    'html_snippet': response.text[:500]  # Debug ke liye
                }
                
        except requests.exceptions.Timeout:
            return {
                'error': 'Request timeout',
                'status': 'failed',
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'error': str(e),
                'status': 'failed',
                'timestamp': datetime.now().isoformat()
            }
    
    def check_inbox(self, email):
        """Email inbox check karega OTP ke liye"""
        try:
            # TempMail ka inbox URL
            inbox_url = f"{self.base_url}/inbox/{email}"
            
            response = self.session.get(
                inbox_url,
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code != 200:
                return {'otp_found': False, 'error': f'HTTP {response.status_code}'}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Messages dhoondhega
            messages = []
            message_elements = soup.find_all(['div', 'tr'], class_=re.compile(r'message|email|inbox'))
            
            for msg in message_elements:
                subject = msg.find(class_=re.compile(r'subject|title'))
                body = msg.find(class_=re.compile(r'body|content|text'))
                
                subject_text = subject.get_text(strip=True) if subject else ''
                body_text = body.get_text(strip=True) if body else ''
                
                # OTP patterns check karega
                full_text = f"{subject_text} {body_text}"
                
                # Common OTP patterns
                otp_patterns = [
                    r'\b\d{4}\b',      # 4 digit
                    r'\b\d{5}\b',      # 5 digit  
                    r'\b\d{6}\b',      # 6 digit
                    r'\b\d{8}\b',      # 8 digit
                    r'OTP[:\s]+(\d+)',
                    r'CODE[:\s]+(\d+)',
                    r'VERIFICATION[:\s]+(\d+)',
                ]
                
                for pattern in otp_patterns:
                    match = re.search(pattern, full_text, re.IGNORECASE)
                    if match:
                        otp = match.group(1) if match.groups() else match.group(0)
                        return {
                            'otp_found': True,
                            'otp': otp,
                            'sender': subject_text[:50],
                            'subject': subject_text,
                            'timestamp': datetime.now().isoformat()
                        }
                
                messages.append({
                    'subject': subject_text,
                    'body_preview': body_text[:100]
                })
            
            return {
                'otp_found': False,
                'messages_count': len(messages),
                'messages': messages[:3]  # Last 3 messages
            }
            
        except Exception as e:
            return {
                'otp_found': False,
                'error': str(e)
            }

# Main execution
if __name__ == "__main__":
    scraper = EmailScraper()
    
    # Action decide karega
    action = os.getenv('GITHUB_EVENT_INPUTS_ACTION', 'create_email')
    
    if action == 'check_otp':
        email = os.getenv('EMAIL_ID', '')
        if email:
            result = scraper.check_inbox(email)
        else:
            result = {'error': 'No email provided for OTP check'}
    else:
        # Default: Create email
        result = scraper.get_temp_email()
    
    # JSON output
    print(json.dumps(result, indent=2))
