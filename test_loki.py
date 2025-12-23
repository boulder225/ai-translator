#!/usr/bin/env python3
"""
Test script for Loki logging integration.
Run this to verify Loki logging is working before deploying.

Usage:
    # Test without Loki (just check configuration):
    python3 test_loki.py
    
    # Test with Loki (set env vars first):
    export LOKI_URL="https://logs-prod-XXX.grafana.net/loki/api/v1/push"
    export LOKI_USERNAME="your-username"
    export LOKI_PASSWORD="your-api-token"
    python3 test_loki.py
"""

import os
import sys
import logging
from pathlib import Path

# Load .env file if it exists
from dotenv import load_dotenv
load_dotenv()

def test_loki_logging():
    """Test that Loki logging handler can be configured correctly."""
    print("=" * 60)
    print("Testing Loki Logging Integration")
    print("=" * 60)
    
    # Check environment variables
    loki_url = os.getenv("LOKI_URL")
    loki_username = os.getenv("LOKI_USERNAME")
    loki_password = os.getenv("LOKI_PASSWORD")
    
    print(f"\n📋 Environment Variables Check:")
    print(f"  LOKI_URL: {'✅ Set' if loki_url else '❌ Not set'}")
    if loki_url:
        print(f"    Value: {loki_url[:50]}...")
    print(f"  LOKI_USERNAME: {'✅ Set' if loki_username else '❌ Not set'}")
    if loki_username:
        print(f"    Value: {loki_username}")
    print(f"  LOKI_PASSWORD: {'✅ Set' if loki_password else '❌ Not set'}")
    if loki_password:
        print(f"    Value: {'*' * len(loki_password)}")
    
    # Check if python-logging-loki-v2 is installed
    print(f"\n📦 Package Check:")
    try:
        import logging_loki
        print(f"  ✅ python-logging-loki-v2 is installed")
        print(f"     Version: {getattr(logging_loki, '__version__', 'unknown')}")
    except ImportError:
        print(f"  ❌ python-logging-loki-v2 is NOT installed")
        print(f"     Install with: pip install python-logging-loki-v2")
        return
    
    # Setup basic logging
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Try to setup Loki handler
    loki_handler = None
    if loki_url and loki_username and loki_password:
        print(f"\n🔧 Setting up Loki Handler...")
        try:
            loki_handler = logging_loki.LokiHandler(
                url=loki_url,
                tags={
                    "application": "legal-translator",
                    "environment": os.getenv("ENVIRONMENT", "test"),
                },
                auth=(loki_username, loki_password),
                version="1",
            )
            loki_handler.setLevel(logging.INFO)
            loki_handler.setFormatter(formatter)
            root_logger.addHandler(loki_handler)
            print(f"  ✅ Loki handler configured successfully!")
        except Exception as e:
            print(f"  ❌ Failed to setup Loki handler: {e}")
            print(f"     Error type: {type(e).__name__}")
            return
    else:
        print(f"\n⚠️  Loki handler NOT configured (missing env vars)")
        print(f"   Set LOKI_URL, LOKI_USERNAME, and LOKI_PASSWORD to enable")
    
    # Check handlers
    print(f"\n📊 Logging Handlers Configured:")
    handler_types = [type(h).__name__ for h in root_logger.handlers]
    for handler_type in handler_types:
        print(f"  ✅ {handler_type}")
    
    if loki_handler:
        print("\n🎉 Loki handler is enabled!")
        print("   Logs will be sent to Grafana Cloud Loki")
        
        # Send test logs
        print("\n" + "=" * 60)
        print("Sending Test Logs to Loki")
        print("=" * 60)
        
        logger = logging.getLogger("test_loki")
        
        logger.info("🧪 Test log: INFO level message from test script")
        logger.warning("🧪 Test log: WARNING level message")
        logger.error("🧪 Test log: ERROR level message")
        
        # Test with structured data
        logger.info("🧪 Test log: Translation job started", extra={
            "job_id": "test-123",
            "source_lang": "fr",
            "target_lang": "it"
        })
        
        print("\n✅ Test logs sent to Loki!")
        print(f"   Check your Grafana Cloud dashboard:")
        print(f"   Query: {{application=\"legal-translator\"}}")
        print(f"   Or: {{application=\"legal-translator\", environment=\"test\"}}")
        print(f"\n💡 Note: Loki rejects logs older than a few hours.")
        print(f"   Make sure your system clock is correct if you see 'timestamp too old' errors.")
    else:
        print("\n💡 To test with Loki:")
        print("   1. Get your Loki URL from Grafana Cloud")
        print("   2. Get your API token from Grafana Cloud")
        print("   3. Set environment variables:")
        print("      export LOKI_URL='https://logs-prod-XXX.grafana.net/loki/api/v1/push'")
        print("      export LOKI_USERNAME='your-username'")
        print("      export LOKI_PASSWORD='your-api-token'")
        print("   4. Run this script again")
    
    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)

if __name__ == "__main__":
    test_loki_logging()
