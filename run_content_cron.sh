#!/bin/bash

# Content Generation Cron Job Runner
# This script runs the content generation cron job

echo "Starting Content Generation Cron Job..."

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Run the cron job
python content_generation_cron.py

echo "Content Generation Cron Job completed."