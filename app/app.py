import os
import time
import redis
import psycopg2
import requests
import threading
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

def get_db():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'monitor-postgres'),
        database=os.getenv('DB_NAME', 'monitor'),
        user=os.getenv('DB_USER', 'admin'),
        password=os.getenv('DB_PASSWORD', 'secret')
    )
    return conn

redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'monitor-redis'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    decode_responses=True
)

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS websites (
            id SERIAL PRIMARY KEY,
            url TEXT NOT NULL,
            status TEXT,
            last_check TIMESTAMP,
            response_time FLOAT
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

def check_website(site_id, url):
    try:
        start = time.time()
        r = requests.get(url, timeout=5, verify=False)
        response_time = round((time.time() - start) * 1000, 2)
        status = 'UP' if r.status_code == 200 else 'DOWN'
    except Exception as e:
        status = 'DOWN'
        response_time = 0
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        UPDATE websites 
        SET status=%s, last_check=NOW(), response_time=%s 
        WHERE id=%s
    ''', (status, response_time, site_id))
    conn.commit()
    cur.close()
    conn.close()
    
    redis_client.set(f'site_{site_id}_status', status)
    redis_client.set(f'site_{site_id}_response_time', response_time)
    
    return status, response_time

def background_checker():
    while True:
        time.sleep(30)
        conn = get_db()
        cur = conn.cursor()
        cur.execute('SELECT id, url FROM websites')
        sites = cur.fetchall()
        cur.close()
        conn.close()
        for site_id, url in sites:
            check_website(site_id, url)
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Checked {len(sites)} sites")

threading.Thread(target=background_checker, daemon=True).start()

# HTML
HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Site Monitor</title>
    <meta http-equiv="refresh" content="20">
    <style>
        body { font-family: Arial; margin: 40px; background: #f0f2f5; }
        .container { max-width: 900px; margin: auto; }
        .card { background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        input { padding: 10px; width: 70%; margin-right: 10px; }
        button { padding: 10px 20px; background: #4CAF50; color: white; border: none; cursor: pointer; }
        .up { color: green; font-weight: bold; }
        .down { color: red; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        .status-up { background: #d4edda; color: #155724; padding: 3px 8px; border-radius: 4px; }
        .status-down { background: #f8d7da; color: #721c24; padding: 3px 8px; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>📡 Site Monitor</h1>
            <form method="POST" action="/add">
                <input type="text" name="url" placeholder="https://example.com" required>
                <button type="submit">Add URL</button>
            </form>
        </div>
        <div class="card">
            <h3>Websites (auto-check every 30 sec)</h3>
            <table>
                <tr><th>URL</th><th>Status</th><th>Response Time</th><th>Action</th></tr>
                {% for site in sites %}
                <tr>
                    <td>{{ site[1] }}</td>
                    <td>
                        {% if site[2] == 'UP' %}
                            <span class="status-up">✅ UP</span>
                        {% elif site[2] == 'DOWN' %}
                            <span class="status-down">❌ DOWN</span>
                        {% else %}
                            ⏳ Pending
                        {% endif %}
                    </td>
                    <td>{% if site[4] %}{{ site[4] }}ms{% else %}—{% endif %}</td>
                    <td><a href="/check/{{ site[0] }}">Check now</a></td>
                </tr>
                {% endfor %}
            </table>
        </div>
    </div>
</body>
</html>
'''

@app.route('/')
def index():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT id, url, status, last_check, response_time FROM websites ORDER BY id DESC')
    sites = cur.fetchall()
    cur.close()
    conn.close()
    return render_template_string(HTML, sites=sites)

@app.route('/add', methods=['POST'])
def add_site():
    url = request.form['url']
    conn = get_db()
    cur = conn.cursor()
    cur.execute('INSERT INTO websites (url) VALUES (%s)', (url,))
    conn.commit()
    cur.close()
    conn.close()
    return '<script>window.location.href="/"</script>'

@app.route('/check/<int:site_id>')
def check_now(site_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT url FROM websites WHERE id = %s', (site_id,))
    url = cur.fetchone()[0]
    cur.close()
    conn.close()
    status, response_time = check_website(site_id, url)
    return f'<script>alert("Site {status} ({response_time}ms)"); window.location.href="/"</script>'

@app.route('/health')
def health():
    return 'OK', 200

if __name__ == '__main__':
    init_db()
    print("🚀 Site Monitor Started!")
    print("📊 Auto-check every 30 seconds")
    print("🌐 Web interface: http://localhost:8080")
    app.run(host='0.0.0.0', port=5000, debug=False)
