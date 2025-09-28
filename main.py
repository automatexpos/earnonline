# main.py
import os, json, socket
from datetime import datetime
from dotenv import load_dotenv

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from contextlib import asynccontextmanager
from supabase import create_client

# Load environment variables from .env file
load_dotenv()

# -------- Config --------
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "change-me")

# Validate required environment variables
if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL environment variable is required")
if not SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY environment variable is required")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        # Try to query the visits table to see if it exists
        supabase.table("visits").select("count", count="exact").limit(1).execute()
        print("✅ Connected to Supabase successfully")
    except Exception as e:
        print(f"⚠️  Supabase connection issue: {e}")
        print("📋 To create the visits table, go to Supabase SQL Editor and run:")
        print("""
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
        """)
    yield
    # Shutdown
    print("Shutting down...")

app = FastAPI(lifespan=lifespan)

def detect_ip(request: Request):
    xff = request.headers.get("x-forwarded-for")
    cf_ip = request.headers.get("cf-connecting-ip")
    real_ip = request.headers.get("x-real-ip")
    ip = xff.split(",")[0].strip() if xff else cf_ip or real_ip or (request.client.host if request.client else None)
    return ip, xff

def reverse_dns(ip: str):
    try:
        name, _, _ = socket.gethostbyaddr(ip)
        return name
    except Exception:
        return None

@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    ip, xff = detect_ip(request)
    ua = request.headers.get("user-agent")
    referer = request.headers.get("referer")
    headers_json = dict(request.headers)
    remote_host = reverse_dns(ip) if ip else None

    # Insert into Supabase
    data = {
        "ts": datetime.utcnow().isoformat(),
        "ip": ip,
        "x_forwarded_for": xff,
        "headers": headers_json,
        "user_agent": ua,
        "referer": referer,
        "remote_host": remote_host,
        # "geo": {...} if you want
    }
    try:
        res = supabase.table("visits").insert(data).execute()
        if hasattr(res, 'error') and res.error:
            print("Supabase error:", res.error)
    except Exception as e:
        print(f"Error inserting into Supabase: {e}")
        # Continue without crashing the app

    html = f"""
    <html><body>
    <h3>Visit recorded at {datetime.utcnow().isoformat()} UTC</h3>
    </body></html>
    """
    return HTMLResponse(content=html)

@app.get("/admin", response_class=HTMLResponse)
def admin_view(key: str = ""):
    if key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    # fetch last 100 visits
    try:
        res = supabase.table("visits").select("*").order("ts", desc=True).limit(100).execute()
        rows = res.data or []
    except Exception as e:
        print(f"Error fetching from Supabase: {e}")
        rows = []
    table_rows = "\n".join(
        "<tr>" + "".join(f"<td>{json.dumps(row.get(col)) if isinstance(row.get(col),(dict,list)) else (row.get(col) or '')}</td>" 
                         for col in ["ts","ip","x_forwarded_for","user_agent","referer","remote_host"]) + "</tr>"
        for row in rows
    )
    html = f"""
    <html><body>
    <h2>Recent visits</h2>
    <table border="1"><thead><tr><th>ts</th><th>ip</th><th>x_forwarded_for</th><th>user_agent</th><th>referer</th><th>remote_host</th></tr></thead>
    <tbody>{table_rows}</tbody></table>
    <p>Total: {len(rows)}</p>
    </body></html>
    """
    return HTMLResponse(content=html)

@app.get("/raw", response_class=PlainTextResponse)
async def raw_info(request: Request):
    ip, xff = detect_ip(request)
    return PlainTextResponse(json.dumps({
        "ip": ip,
        "x_forwarded_for": xff,
        "headers": dict(request.headers),
    }, indent=2))

if __name__ == "__main__":
    import uvicorn
    print("Starting FastAPI server...")
    print("Visit: http://localhost:8000")
    print("Admin: http://localhost:8000/admin?key=" + ADMIN_KEY)
    print("Raw info: http://localhost:8000/raw")
    print("Press Ctrl+C to stop")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
