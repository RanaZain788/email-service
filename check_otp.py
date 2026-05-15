import os
import json
import sys
from scraper import EmailScraper
from firebase_admin import credentials, initialize_app, db
import firebase_admin

def main():
    email_id = os.getenv('EMAIL_ID', '')
    
    if not email_id:
        # Firebase se last active email lega
        try:
            if not firebase_admin._apps:
                import json
                cred_info = json.loads(os.getenv('FIREBASE_TOKEN'))
                cred = credentials.Certificate(cred_info)
                initialize_app(cred, {'databaseURL': os.getenv('FIREBASE_URL')})
            
            ref = db.reference('/emails')
            # Last active email
            emails = ref.order_by_child('status').equal_to('active').get()
            
            if emails:
                last_email = list(emails.values())[-1]
                email_id = last_email.get('email', '')
                print(f"Using last active email: {email_id}", file=sys.stderr)
        except Exception as e:
            print(f"Firebase error: {e}", file=sys.stderr)
    
    if not email_id:
        print(json.dumps({
            'otp_found': False,
            'error': 'No active email found'
        }))
        return
    
    # OTP check karega
    scraper = EmailScraper()
    result = scraper.check_inbox(email_id)
    
    # Agar OTP mila to Firebase mein save karega
    if result.get('otp_found'):
        try:
            if not firebase_admin._apps:
                import json
                cred_info = json.loads(os.getenv('FIREBASE_TOKEN'))
                cred = credentials.Certificate(cred_info)
                initialize_app(cred, {'databaseURL': os.getenv('FIREBASE_URL')})
            
            otp_ref = db.reference('/otps')
            otp_ref.push({
                'email': email_id,
                'otp': result['otp'],
                'timestamp': result['timestamp'],
                'sender': result.get('sender', '')
            })
            print("OTP saved to Firebase!", file=sys.stderr)
        except Exception as e:
            print(f"Error saving OTP: {e}", file=sys.stderr)
    
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
