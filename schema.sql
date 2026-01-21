-- Emily Digital Marketing Agent Database Schema
-- Using Supabase Auth for user management

-- Create profiles table to extend Supabase Auth users
CREATE TABLE IF NOT EXISTS profiles (
    id UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
    name TEXT,
    avatar_url TEXT,
    onboarding_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Basic Business Information
    business_name TEXT,
    business_type TEXT[], -- Array of business types
    industry TEXT[], -- Array of industries
    business_description TEXT,
    target_audience TEXT[], -- Array of target audiences
    unique_value_proposition TEXT,
    
    -- Brand & Contact Information
    brand_voice TEXT,
    brand_tone TEXT,
    website_url TEXT,
    phone_number TEXT,
    street_address TEXT,
    city TEXT,
    state TEXT,
    country TEXT,
    timezone TEXT,
    
    -- Social Media & Goals
    social_media_platforms TEXT[], -- Array of platforms
    primary_goals TEXT[], -- Array of goals
    key_metrics_to_track TEXT[], -- Array of metrics
    
    -- Content Strategy
    monthly_budget_range TEXT,
    posting_frequency TEXT,
    preferred_content_types TEXT[], -- Array of content types
    content_themes TEXT[], -- Array of themes
    
    -- Market & Competition
    main_competitors TEXT,
    market_position TEXT,
    products_or_services TEXT,
    
    -- Campaign Planning
    important_launch_dates TEXT,
    planned_promotions_or_campaigns TEXT,
    top_performing_content_types TEXT[], -- Array of content types
    best_time_to_post TEXT[], -- Array of times
    
    -- Performance & Customer
    successful_campaigns TEXT,
    successful_content_url TEXT,
    hashtags_that_work_well TEXT,
    customer_pain_points TEXT,
    typical_customer_journey TEXT,
    
    -- Automation & Platform Details
    automation_level TEXT,
    platform_specific_tone JSONB, -- JSON object for platform-specific tones
    current_presence TEXT[], -- Array of current presence
    focus_areas TEXT[], -- Array of focus areas
    platform_details JSONB, -- JSON object for platform details
    
    -- Platform-specific links and accounts
    facebook_page_name TEXT,
    instagram_profile_link TEXT,
    linkedin_company_link TEXT,
    youtube_channel_link TEXT,
    x_twitter_profile TEXT,
    google_business_profile TEXT,
    google_ads_account TEXT,
    whatsapp_business TEXT,
    email_marketing_platform TEXT,
    meta_ads_facebook BOOLEAN DEFAULT FALSE,
    meta_ads_instagram BOOLEAN DEFAULT FALSE
);

-- Enable Row Level Security (RLS)
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

-- Create policy for users to access their own profile
CREATE POLICY "Users can view own profile" ON profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON profiles
    FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users can insert own profile" ON profiles
    FOR INSERT WITH CHECK (auth.uid() = id);

-- Create a function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_profiles_updated_at 
    BEFORE UPDATE ON profiles 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- OAuth States Table (for CSRF protection during OAuth flows)
CREATE TABLE IF NOT EXISTS oauth_states (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  state VARCHAR(100) NOT NULL UNIQUE,
  platform VARCHAR(50) NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  expires_at TIMESTAMP WITH TIME ZONE NOT NULL,

  -- Ensure unique state per user/platform combination
  UNIQUE(user_id, platform)
);

-- Indexes for better performance
CREATE INDEX idx_oauth_states_user_id ON oauth_states(user_id);
CREATE INDEX idx_oauth_states_state ON oauth_states(state);
CREATE INDEX idx_oauth_states_platform ON oauth_states(platform);

-- RLS (Row Level Security) policies
ALTER TABLE oauth_states ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own OAuth states
CREATE POLICY "Users can view own oauth states" ON oauth_states
  FOR SELECT USING (auth.uid() = user_id);

-- Policy: Users can insert their own OAuth states
CREATE POLICY "Users can insert own oauth states" ON oauth_states
  FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Policy: Users can delete their own OAuth states
CREATE POLICY "Users can delete own oauth states" ON oauth_states
  FOR DELETE USING (auth.uid() = user_id);

-- Clean up expired states periodically (optional)
-- You can run this as a cron job or scheduled function
CREATE OR REPLACE FUNCTION cleanup_expired_oauth_states()
RETURNS INTEGER AS $$
DECLARE
  deleted_count INTEGER;
BEGIN
  DELETE FROM oauth_states WHERE expires_at < NOW();
  GET DIAGNOSTICS deleted_count = ROW_COUNT;
  RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Social Media Calendars Table (parent table for calendar entries)
CREATE TABLE IF NOT EXISTS social_media_calendars (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable Row Level Security (RLS) for social_media_calendars
ALTER TABLE social_media_calendars ENABLE ROW LEVEL SECURITY;

-- Create policy for users to access their own calendars
CREATE POLICY "Users can view own calendars" ON social_media_calendars
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own calendars" ON social_media_calendars
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own calendars" ON social_media_calendars
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own calendars" ON social_media_calendars
    FOR DELETE USING (auth.uid() = user_id);

-- Create trigger to automatically update updated_at for social_media_calendars
CREATE TRIGGER update_social_media_calendars_updated_at
    BEFORE UPDATE ON social_media_calendars
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Indexes for better performance on social_media_calendars
CREATE INDEX idx_social_media_calendars_user_id ON social_media_calendars(user_id);
CREATE INDEX idx_social_media_calendars_status ON social_media_calendars(status);

-- Calendar Entries Table (for content calendar management)
create table public.calendar_entries (
  id uuid not null default gen_random_uuid (),
  calendar_id uuid null,
  entry_date date not null,
  content_type text not null,
  content_theme text not null,
  topic text not null,
  platform text not null,
  hook_type text null,
  hook_length text null,
  tone text null,
  creativity text null,
  text_in_image text null,
  visual_style text null,
  status text null default 'draft'::text,
  scheduled_time time without time zone null,
  created_at timestamp with time zone null default now(),
  updated_at timestamp with time zone null default now(),
  content boolean not null default false,
  constraint calendar_entries_pkey primary key (id),
  constraint calendar_entries_calendar_id_fkey foreign KEY (calendar_id) references social_media_calendars (id) on delete CASCADE
) TABLESPACE pg_default;

create index IF not exists idx_calendar_entries_calendar_date on public.calendar_entries using btree (calendar_id, entry_date) TABLESPACE pg_default;

create index IF not exists idx_calendar_entries_status on public.calendar_entries using btree (status) TABLESPACE pg_default;-- Function to handle new user signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, name, onboarding_completed)
  VALUES (NEW.id, NEW.raw_user_meta_data->>'name', FALSE)
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Drop existing trigger if it exists, then create new one
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();




