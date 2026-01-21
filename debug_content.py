#!/usr/bin/env python3
"""
Debug Content Field Values
Check what values are stored in the content field
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def debug_content():
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

    if not supabase_url or not supabase_key:
        print("ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        return

    supabase = create_client(supabase_url, supabase_key)

    print("=== DEBUGGING CONTENT FIELD VALUES ===")

    # Check all entries
    print("\n1. All calendar entries (first 10):")
    all_entries = supabase.table('calendar_entries').select('id, content, topic').limit(10).execute()

    for entry in all_entries.data:
        print(f"  ID: {entry['id']}")
        print(f"  Content: {entry['content']} (type: {type(entry['content'])})")
        print(f"  Topic: {entry['topic']}")
        print("  ---")

    print(f"Total entries: {len(all_entries.data)}")

    # Check entries with content = false
    print("\n2. Entries with content = False:")
    false_entries = supabase.table('calendar_entries').select('id, content, topic').eq('content', False).execute()
    print(f"Found: {len(false_entries.data)} entries")

    # Check entries with content != true
    print("\n3. Entries with content != True:")
    neq_true_entries = supabase.table('calendar_entries').select('id, content, topic').neq('content', True).execute()
    print(f"Found: {len(neq_true_entries.data)} entries")

    # Check entries with content IS NULL
    print("\n4. Entries with content IS NULL:")
    null_entries = supabase.table('calendar_entries').select('id, content, topic').is_('content', 'null').execute()
    print(f"Found: {len(null_entries.data)} entries")

    print("\n=== END DEBUG ===")

if __name__ == "__main__":
    debug_content()