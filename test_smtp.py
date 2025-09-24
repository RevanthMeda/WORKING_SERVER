
#!/usr/bin/env python3
import os
import smtplib
import base64
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Force reload environment variables
load_dotenv(override=True)

def test_smtp_connection():
    """Test SMTP connection with current credentials"""
    
    smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT', '587'))
    smtp_username = os.environ.get('SMTP_USERNAME', '')
    smtp_password = os.environ.get('SMTP_PASSWORD', '')
    
    print(f"📧 Testing SMTP connection...")
    print(f"Server: {smtp_server}:{smtp_port}")
    print(f"Username: {smtp_username}")
    print(f"Password: {'*' * len(smtp_password) if smtp_password else 'NOT_SET'}")
    print(f"Password length: {len(smtp_password)}")
    
    if not smtp_password or smtp_password == 'PUT_YOUR_ACTUAL_16_CHAR_GMAIL_APP_PASSWORD_HERE':
        print("❌ SMTP_PASSWORD not properly set in .env file")
        return False
    
    try:
        print("\n🔗 Attempting connection...")
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        
        print("🔐 Attempting login...")
        server.login(smtp_username, smtp_password)
        
        print("✅ SMTP connection successful!")
        server.quit()
        return True
        
    except Exception as e:
        print(f"❌ SMTP connection failed: {e}")
        return False

if __name__ == '__main__':
    print("🧪 SMTP Connection Test")
    print("=" * 30)
    success = test_smtp_connection()
    print("\n" + "=" * 30)
    print("✅ Test completed successfully!" if success else "❌ Test failed!")
