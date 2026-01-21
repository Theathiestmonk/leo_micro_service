#!/usr/bin/env python3
"""
Reset Calendar Entries for Testing
Sets a few calendar entries back to content = false for testing image generation
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def reset_entries():
    """Reset a few entries for testing"""
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

    if not supabase_url or not supabase_key:
        print("ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env file")
        return

    supabase = create_client(supabase_url, supabase_key)

    print("Resetting calendar entries for testing...")

    try:
        # Get the most recent entries
        response = supabase.table('calendar_entries').select('id, topic, platform, content').order('created_at', desc=True).limit(3).execute()

        if not response.data:
            print("No calendar entries found")
            return

        print(f"Found {len(response.data)} recent entries")

        for entry in response.data:
            print(f"Resetting entry {entry['id']}: {entry['topic']} (platform: {entry['platform']})")

            # Reset to content = false for testing
            supabase.table('calendar_entries').update({
                'content': False,
                'status': 'pending_generation'
            }).eq('id', entry['id']).execute()

        print("\nSUCCESS: Reset 3 entries to content = false")
        print("Run the cron job now to test image generation!")

    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    reset_entries()