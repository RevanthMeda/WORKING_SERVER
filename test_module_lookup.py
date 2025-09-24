#!/usr/bin/env python3
"""
Test script to verify module lookup functionality
"""
import requests
import json

def test_module_lookup(company, model):
    """Test the module lookup API endpoint"""
    url = "http://localhost:5000/io-builder/api/module-lookup"
    
    payload = {
        "company": company,
        "model": model
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        
        print(f"\n=== Testing Module Lookup: {company} {model} ===")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Success: {data.get('success')}")
            
            if data.get('success') and data.get('module'):
                module = data['module']
                print(f"Description: {module.get('description')}")
                print(f"Digital Inputs: {module.get('digital_inputs')}")
                print(f"Digital Outputs: {module.get('digital_outputs')}")
                print(f"Analog Inputs: {module.get('analog_inputs')}")
                print(f"Analog Outputs: {module.get('analog_outputs')}")
                print(f"Source: {data.get('source')}")
            else:
                print(f"Message: {data.get('message')}")
        else:
            print(f"Error Response: {response.text}")
            
    except Exception as e:
        print(f"Error: {e}")

# Test various modules
test_cases = [
    ("ABB", "DA501"),      # Should find ABB DA501 module
    ("", "DA501"),         # Should find DA501 without vendor
    ("ABB", "DI810"),      # Should find ABB DI810 module
    ("", "DO810"),         # Should find DO810 without vendor
    ("SIEMENS", "SM1221"), # Should find Siemens SM1221
    ("", "SM1231"),        # Should find SM1231 without vendor
    ("XYZ", "UNKNOWN"),    # Should not find this module
]

for company, model in test_cases:
    test_module_lookup(company, model)

print("\n=== Test completed ===")