from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import os
import json
import socket
from datetime import datetime

# Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "change-me")

# Initialize Supabase client (lazy loading)
_supabase_client = None

def get_supabase():
    global _supabase_client
    if _supabase_client is None and SUPABASE_URL and SUPABASE_KEY:
        try:
            from supabase import create_client
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception as e:
            print(f"Supabase initialization error: {e}")
    return _supabase_client

def detect_ip(headers):
    """Extract visitor IP from request headers"""
    xff = headers.get("x-forwarded-for", "")
    cf_ip = headers.get("cf-connecting-ip", "")
    real_ip = headers.get("x-real-ip", "")
    
    if xff:
        return xff.split(",")[0].strip(), xff
    return cf_ip or real_ip or "unknown", None

def reverse_dns(ip_address):
    """Perform reverse DNS lookup"""
    try:
        if ip_address and ip_address != "unknown":
            hostname, _, _ = socket.gethostbyaddr(ip_address)
            return hostname
    except:
        pass
    return None

def log_visit(headers, path):
    """Log visit to Supabase database"""
    supabase = get_supabase()
    if not supabase:
        return False
    
    try:
        ip, xff = detect_ip(headers)
        user_agent = headers.get("user-agent", "")
        referer = headers.get("referer", "")
        remote_host = reverse_dns(ip)
        
        visit_data = {
            "ts": datetime.utcnow().isoformat(),
            "ip": ip,
            "x_forwarded_for": xff,
            "headers": dict(headers),
            "user_agent": user_agent,
            "referer": referer,
            "remote_host": remote_host,
        }
        
        result = supabase.table("visits").insert(visit_data).execute()
        return True
    except Exception as e:
        print(f"Database logging error: {e}")
        return False

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # Parse URL and query parameters
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            query_params = parse_qs(parsed_url.query)
            
            # Convert headers to dict
            headers = {}
            for name, value in self.headers.items():
                headers[name.lower()] = value
            
            # Get visitor IP
            ip, xff = detect_ip(headers)
            
            # Route handling
            if path == "/" or path == "":
                self.handle_home(headers, ip)
            elif path == "/raw":
                self.handle_raw(headers, ip, xff)
            elif path == "/admin":
                admin_key = query_params.get('key', [''])[0]
                self.handle_admin(admin_key)
            else:
                self.handle_404()
                
        except Exception as e:
            print(f"Request handling error: {e}")
            self.send_error(500, f"Internal Server Error: {str(e)}")
    
    def handle_home(self, headers, ip):
        """Handle main landing page"""
        # Log the visit
        log_visit(headers, "/")
        
        user_agent = headers.get("user-agent", "Unknown")
        timestamp = datetime.utcnow().isoformat()
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>IP Tracker - Visit Recorded</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .container {{ max-width: 600px; }}
        .success {{ color: #28a745; }}
        .info {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1 class="success">✅ Visit Recorded Successfully!</h1>
        
        <div class="info">
            <p><strong>Timestamp:</strong> {timestamp} UTC</p>
            <p><strong>Your IP Address:</strong> {ip}</p>
            <p><strong>User Agent:</strong> {user_agent}</p>
        </div>
        
        <hr>
        <p>
            <a href="/api/raw">📊 View Raw Data</a> | 
            <a href="/api/admin?key={ADMIN_KEY}">🔧 Admin Dashboard</a>
        </p>
    </div>
</body>
</html>
        """
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(html_content.encode('utf-8'))
    
    def handle_raw(self, headers, ip, xff):
        """Handle raw JSON data endpoint"""
        data = {
            "timestamp": datetime.utcnow().isoformat(),
            "ip": ip,
            "x_forwarded_for": xff,
            "headers": dict(headers),
            "remote_host": reverse_dns(ip)
        }
        
        json_output = json.dumps(data, indent=2)
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json_output.encode('utf-8'))
    
    def handle_admin(self, admin_key):
        """Handle admin dashboard"""
        if admin_key != ADMIN_KEY:
            self.send_response(401)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<h1>401 Unauthorized</h1><p>Invalid admin key</p>')
            return
        
        # Fetch recent visits
        visits = []
        supabase = get_supabase()
        if supabase:
            try:
                result = supabase.table("visits").select("*").order("ts", desc=True).limit(100).execute()
                visits = result.data or []
            except Exception as e:
                print(f"Database fetch error: {e}")
        
        # Generate table rows
        table_rows = ""
        for visit in visits:
            table_rows += "<tr>"
            for column in ["ts", "ip", "x_forwarded_for", "user_agent", "referer", "remote_host"]:
                value = visit.get(column, "")
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                elif value is None:
                    value = ""
                table_rows += f"<td>{str(value)[:100]}</td>"  # Limit cell content
            table_rows += "</tr>"
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Admin Dashboard - IP Tracker</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .stats {{ background: #e9ecef; padding: 15px; border-radius: 5px; margin: 20px 0; }}
    </style>
</head>
<body>
    <h1>🔧 Admin Dashboard</h1>
    
    <div class="stats">
        <p><strong>Total Visits Shown:</strong> {len(visits)}</p>
        <p><strong>Last Updated:</strong> {datetime.utcnow().isoformat()} UTC</p>
    </div>
    
    <table>
        <thead>
            <tr>
                <th>Timestamp</th>
                <th>IP Address</th>
                <th>X-Forwarded-For</th>
                <th>User Agent</th>
                <th>Referer</th>
                <th>Remote Host</th>
            </tr>
        </thead>
        <tbody>
            {table_rows}
        </tbody>
    </table>
    
    <hr>
    <p>
        <a href="/api/">← Back to Home</a> | 
        <a href="/api/raw">📊 Raw Data</a>
    </p>
</body>
</html>
        """
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(html_content.encode('utf-8'))
    
    def handle_404(self):
        """Handle 404 Not Found"""
        html_content = """
<!DOCTYPE html>
<html>
<head><title>404 - Not Found</title></head>
<body>
    <h1>404 - Page Not Found</h1>
    <p><a href="/api/">← Go to Home</a></p>
</body>
</html>
        """
        
        self.send_response(404)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(html_content.encode('utf-8'))
    
    def do_POST(self):
        """Handle POST requests (redirect to GET for now)"""
        self.do_GET()
    
    def log_message(self, format, *args):
        """Suppress default request logging"""
        pass