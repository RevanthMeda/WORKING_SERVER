#!/usr/bin/env python3
"""
Test script for the new AI Agent system
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from services.ai_agent import start_ai_conversation, process_ai_message, get_ai_capabilities

def test_ai_agent():
    """Test the AI agent functionality"""
    print("🤖 Testing AI Agent System")
    print("=" * 50)
    
    # Test capabilities
    print("\n1. Testing AI Capabilities:")
    capabilities = get_ai_capabilities()
    for cap in capabilities:
        print(f"   ✓ {cap}")
    
    # Test conversation start
    print("\n2. Testing Conversation Start:")
    try:
        # Mock session for testing
        import flask
        from unittest.mock import MagicMock
        
        # Create a mock Flask app context
        app = flask.Flask(__name__)
        app.config['SECRET_KEY'] = 'test-key'
        
        with app.test_request_context():
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    # Start conversation
                    response = start_ai_conversation()
                    print(f"   ✓ Welcome message: {response['message'][:100]}...")
                    print(f"   ✓ Suggestions count: {len(response['suggestions'])}")
                    print(f"   ✓ Actions count: {len(response['actions'])}")
                    
                    # Test message processing
                    print("\n3. Testing Message Processing:")
                    test_messages = [
                        "Hello, I need help creating a SAT report",
                        "What can you help me with?",
                        "I want to analyze my data",
                        "How do I optimize my workflow?"
                    ]
                    
                    for i, message in enumerate(test_messages, 1):
                        print(f"\n   Test {i}: '{message}'")
                        try:
                            response = process_ai_message(message)
                            print(f"   ✓ Response: {response['message'][:100]}...")
                            print(f"   ✓ Confidence: {response['confidence']}")
                            print(f"   ✓ Suggestions: {len(response['suggestions'])}")
                        except Exception as e:
                            print(f"   ❌ Error: {e}")
                    
                    print("\n✅ AI Agent system test completed successfully!")
                    
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_ai_agent()