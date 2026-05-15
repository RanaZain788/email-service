import requests
from bs4 import BeautifulSoup
import json
import re
import os
from datetime import datetime

class EmailScraper:
    def __init__(self):
        self.base_url = "https://tempmail.ninja"
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
    def get_temp_email(self):
        """TempMail.Ninja se naya email lega"""
        try:
            # Pehle homepage se email fetch karega
            response = self.session.get(self.base_url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Email dhoondhega - class name check karega
                email_span = soup.find('span', class_='main-email')
                
                if email_span:
                    email = email_span.get_text(strip=True)
                    # Email validation
                    if re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
                        return {
                            'email': email,
                            'timestamp': datetime.now().isoformat(),
                            'status': 'active',
                            'source': 'tempmail.ninja'
                        }
            
            return None
            
        except Exception as e:
            print(f"Error fetching email: {str(e)}")
            return None
    
    def check_inbox(self, email):
        """Email ka inbox check karega OTP ke liye"""
        try:
            # TempMail API ya inbox page se check karega
            inbox_url = f"{self.base_url}/api/inbox/{email}"
            
            response = self.session.get(inbox_url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # OTP wala email dhoondhega
                for message in data.get('messages', []):
                    subject = message.get('subject', '').lower()
                    body = message.get('body', '').lower()
                    
                    # OTP patterns check karega
                    otp_patterns = [
                        r'\b\d{4,8}\b',  # 4-8 digit numbers
                        r'otp[\s:]+(\d+)',
                        r'code[\s:]+(\d+)',
                        r'verification[\s:]+(\d+)',
                        r'confirm[\s:]+(\d+)'
                    ]
                    
                    for pattern in otp_patterns:
                        match = re.search(pattern, subject + ' ' + body)
                        if match:
                            return {
                                'otp_found': True,
                                'otp': match.group(1),
                                'sender': message.get('from', ''),
                                'subject': message.get('subject', ''),
                                'timestamp': datetime.now().isoformat()
                            }
                
                return {'otp_found': False, 'messages': len(data.get('messages', []))}
            
            return {'otp_found': False, 'error': 'Failed to check inbox'}
            
        except Exception as e:
            print(f"Error checking inbox: {str(e)}")
            return {'otp_found': False, 'error': str(e)}
    
    def save_to_firebase(self, data, firebase_url, firebase_token):
        """Firebase Realtime Database mein save karega"""
        try:
            import firebase_admin
            from firebase_admin import credentials, db
            
            # Firebase initialize (agar pehle se nahi hua)
            if not firebase_admin._apps:
                cred = credentials.Certificate(firebase_token)
                firebase_admin.initialize_app(cred, {
                    'databaseURL': firebase_url
                })
            
            ref = db.reference('/emails')
            ref.push(data)
            
            return True
            
        except Exception as e:
            print(f"Firebase error: {str(e)}")
            # Fallback: JSON file mein save karega
            self._save_local(data)
            return False
    
    def _save_local(self, data):
        """Local JSON file mein backup save karega"""
        try:
            with open('emails_data.json', 'a') as f:
                json.dump(data, f)
                f.write('\n')
        except:
            pass

# Main execution
if __name__ == "__main__":
    scraper = EmailScraper()
    
    # Email fetch karega
    email_data = scraper.get_temp_email()
    
    if email_data:
        print(json.dumps(email_data, indent=2))
        
        # Firebase mein save karega (env variables se)
        firebase_url = os.getenv('FIREBASE_URL')
        firebase_token = os.getenv('FIREBASE_TOKEN')
        
        if firebase_url and firebase_token:
            scraper.save_to_firebase(email_data, firebase_url, firebase_token)
    else:
        print(json.dumps({'error': 'Failed to get email', 'status': 'failed'}))