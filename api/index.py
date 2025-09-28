# api/index.py - Vercel entry point
import os, json, socket
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from supabase import create_client

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
    yield
    # Shutdown
    print("Shutting down...")

app = FastAPI(lifespan=lifespan, title="IP Detection Service")

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
    }
    try:
        res = supabase.table("visits").insert(data).execute()
        if hasattr(res, 'error') and res.error:
            print("Supabase error:", res.error)
    except Exception as e:
        print(f"Error inserting into Supabase: {e}")

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>IP Detection Service</title>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            .info {{ background: #f0f8ff; padding: 20px; border-radius: 8px; }}
            .ip {{ font-size: 24px; font-weight: bold; color: #0066cc; }}
        </style>
    </head>
    <body>
        <div class="info">
            <h2>🌐 IP Detection Service</h2>
            <p class="ip">Your IP: {ip or 'Unknown'}</p>
            <p><strong>Timestamp:</strong> {datetime.utcnow().isoformat()} UTC</p>
            <p><strong>User Agent:</strong> {ua or 'Unknown'}</p>
            {f'<p><strong>Referer:</strong> {referer}</p>' if referer else ''}
            {f'<p><strong>Hostname:</strong> {remote_host}</p>' if remote_host else ''}
        </div>
        <p><a href="/raw">View Raw Data</a></p>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/admin", response_class=HTMLResponse)
def admin_view(key: str = ""):
    if key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
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
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin - Recent Visits</title>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            .count {{ background: #e8f5e8; padding: 10px; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <h2>📊 Recent Visits</h2>
        <div class="count">Total visits: {len(rows)}</div>
        <br>
        <table>
            <thead>
                <tr><th>Timestamp</th><th>IP</th><th>X-Forwarded-For</th><th>User Agent</th><th>Referer</th><th>Hostname</th></tr>
            </thead>
            <tbody>{table_rows}</tbody>
        </table>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/raw", response_class=PlainTextResponse)
async def raw_info(request: Request):
    ip, xff = detect_ip(request)
    return PlainTextResponse(json.dumps({
        "ip": ip,
        "x_forwarded_for": xff,
        "headers": dict(request.headers),
        "timestamp": datetime.utcnow().isoformat()
    }, indent=2))

# Vercel handler
handler = app