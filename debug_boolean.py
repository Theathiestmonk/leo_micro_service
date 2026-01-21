#!/usr/bin/env python3
"""
Debug Boolean Query Issues
Test different ways to query boolean values in Supabase
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def debug_boolean_queries():
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

    if not supabase_url or not supabase_key:
        print("ERROR: Missing environment variables")
        return

    supabase = create_client(supabase_url, supabase_key)

    print("=== DEBUGGING BOOLEAN QUERIES ===")

    # Check sample entries
    print("\n1. Sample calendar entries:")
    entries = supabase.table('calendar_entries').select('id, content, topic').limit(5).execute()

    for entry in entries.data:
        print(f"  ID: {entry['id']}")
        print(f"  Content: {entry['content']} (type: {type(entry['content'])})")
        print(f"  Topic: {entry['topic']}")
        print("  ---")

    # Test different query methods
    print("\n2. Testing different boolean queries:")

    # Current method used in cron job
    neq_true = supabase.table('calendar_entries').select('id, content').neq('content', True).execute()
    print(f"neq('content', True): {len(neq_true.data)} entries")

    # Alternative method
    eq_false = supabase.table('calendar_entries').select('id, content').eq('content', False).execute()
    print(f"eq('content', False): {len(eq_false.data)} entries")

    # Check if there are actually any false values
    print("\n3. Checking for actual false values:")
    all_entries = supabase.table('calendar_entries').select('content').execute()
    false_count = sum(1 for entry in all_entries.data if entry['content'] is False)
    true_count = sum(1 for entry in all_entries.data if entry['content'] is True)
    null_count = sum(1 for entry in all_entries.data if entry['content'] is None)

    print(f"Total entries: {len(all_entries.data)}")
    print(f"Content = false: {false_count}")
    print(f"Content = true: {true_count}")
    print(f"Content = null: {null_count}")

    print("\n=== END DEBUG ===")

if __name__ == "__main__":
    debug_boolean_queries()