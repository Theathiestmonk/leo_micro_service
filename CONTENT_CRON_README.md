# Content Generation Cron Job

This cron job automatically processes calendar entries that need content generation and creates content using the ContentCreationAgent.

## How It Works

1. **Checks calendar_entries table** for entries where `content = false`
2. **Extracts content parameters** from each entry:
   - `content_type`, `content_theme`, `topic`, `platform`
   - `hook_type`, `hook_length`, `tone`, `creativity`
   - `text_in_image`, `visual_style`
3. **Gets user context** from the related calendar (`calendar_id.user_id`)
4. **Generates content** using ContentCreationAgent
5. **Creates images** using OpenAI DALL-E based on the content and saves them locally
6. **Updates the entry** to set `content = true` and `status = 'content_generated'`

## Setup

### 1. Environment Variables

Make sure your `.env` file contains:
```
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
OPENAI_API_KEY=your_openai_api_key
GEMINI_API_KEY=your_gemini_api_key
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Database Schema

Run the `schema.sql` file in your Supabase database to create the required tables:
- `social_media_calendars`
- `calendar_entries`

## Running the Cron Job

### Manual Execution

**Linux/Mac:**
```bash
./run_content_cron.sh
```

**Windows:**
```cmd
run_content_cron.bat
```

**Direct Python:**
```bash
python content_generation_cron.py
```

### Automated Scheduling

#### Linux/Mac (crontab)
Add to crontab to run every hour:
```bash
crontab -e
```
Add this line:
```
0 * * * * cd /path/to/your/project && ./run_content_cron.sh
```

#### Windows (Task Scheduler)
1. Open Task Scheduler
2. Create a new task
3. Set trigger (e.g., daily at specific time)
4. Set action to run `run_content_cron.bat`

## File Structure

```
generated_images/          # Generated images are saved here
content_generation_cron.py # Main cron job script
run_content_cron.sh        # Linux/Mac runner script
run_content_cron.bat       # Windows runner script
CONTENT_CRON_README.md     # This file
```

## Generated Images

Images are saved in the `generated_images/` directory with filenames in the format:
```
{topic}_{entry_id}.png
```

For example: `social_media_marketing_uuid-1234.png`

## Database Updates

After processing, the cron job updates calendar entries:
- `content`: `false` → `true`
- `status`: current status → `'content_generated'`
- `updated_at`: timestamp updated

## Error Handling

- Individual entry errors don't stop the entire process
- Errors are logged with entry IDs for debugging
- Failed entries remain with `content = false` for retry

## Testing

### Quick Test Setup

1. **Update test script** with your actual user ID:
   ```python
   # In test_insert_calendar_entry.py, replace this line:
   sample_user_id = "your-user-id-here"  # Replace with actual user ID
   ```

2. **Insert test data:**
   ```bash
   python test_insert_calendar_entry.py
   ```

3. **Run the cron job:**
   ```bash
   python content_generation_cron.py
   ```

4. **Verify results:**
   - Check that calendar entries have `content = true`
   - Look for generated images in `generated_images/` directory

### Manual Testing

To test the cron job manually:
1. Insert a calendar entry with `content = false`
2. Run the cron job
3. Check that `content` is now `true` and an image was generated