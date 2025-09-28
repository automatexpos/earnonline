# IP Detection & Visitor Tracking API

A FastAPI application that detects visitor IP addresses and logs visits to Supabase, deployed on Vercel.

## Features

- 🌐 IP address detection (supports X-Forwarded-For, CF-Connecting-IP, X-Real-IP)
- 📊 Visitor tracking with detailed headers and metadata
- 🔍 Reverse DNS lookup
- 📋 Admin dashboard to view visit logs
- 🚀 Serverless deployment on Vercel

## Endpoints

- `/` - Main landing page (records visits)
- `/raw` - Returns visitor IP and headers in JSON format
- `/admin?key=YOUR_ADMIN_KEY` - Admin dashboard to view recorded visits

## Local Development

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.template` to `.env` and fill in your values
4. Run: `python main.py`
5. Visit: `http://localhost:8000`

## Environment Variables

Set these in your Vercel dashboard:

- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_KEY` - Your Supabase service key
- `ADMIN_KEY` - Password for admin dashboard

## Database Setup

Create the visits table in Supabase:

```sql
CREATE TABLE visits (
    id SERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip INET,
    x_forwarded_for TEXT,
    headers JSONB,
    user_agent TEXT,
    referer TEXT,
    remote_host TEXT
);
```

## Deployment

This app is configured for Vercel deployment. Simply connect your GitHub repository to Vercel and it will deploy automatically.