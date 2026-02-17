import sqlite3
import os
import asyncio
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, g, send_from_directory
from playwright.sync_api import sync_playwright

DATABASE = 'tweets.db'
app = Flask(__name__)

# PWA static files
@app.route('/manifest.json')
def manifest():
    return send_from_directory('.', 'manifest.json', mimetype='application/manifest+json')

@app.route('/sw.js')
def service_worker():
    return send_from_directory('.', 'sw.js', mimetype='application/javascript')

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''
            CREATE TABLE IF NOT EXISTS tweets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                username TEXT,
                tweet_text TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                posted BOOLEAN DEFAULT 0,
                posted_at DATETIME
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tweet_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                feedback TEXT,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tweet_id) REFERENCES tweets(id)
            )
        ''')
        db.commit()

# Fetch tweet content using Playwright
def fetch_tweet_content(tweet_url):
    """Fetch tweet text and username using Playwright"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            context = browser.contexts[0]
            page = context.new_page()
            
            page.goto(tweet_url, timeout=15000)
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            
            # Try to extract tweet text - selector pattern for X
            tweet_text = ""
            username = ""
            
            # Common selectors for tweet content
            selectors = [
                '[data-testid="tweetText"]',
                '.css-901oao.r-hwyvb4.r-1qd0xha.r-a023e6.r-16dba41.r-ad9z0x.r-bcqeeo.r-qvutc0',
                'article[role="article"] div[lang]'
            ]
            
            for sel in selectors:
                try:
                    elements = page.query_selector_all(sel)
                    if elements:
                        tweet_text = elements[0].inner_text()
                        break
                except:
                    continue
            
            # Extract username from URL or page
            if '/status/' in tweet_url:
                parts = tweet_url.split('/')
                for i, part in enumerate(parts):
                    if part == 'status':
                        username = parts[i-1].replace('@', '')
                        break
            
            browser.close()
            
            return {
                'text': tweet_text[:500] if tweet_text else "",
                'username': username
            }
    except Exception as e:
        print(f"Error fetching tweet: {e}")
        return {'text': '', 'username': ''}

# Generate contextual replies based on tweet content
def generate_reply_content(tweet_text, username):
    """Generate contextual replies based on tweet content"""
    if not tweet_text:
        return ["solid point", "agreed", "preach", "ngl this hits", "facts"]
    
    text_lower = tweet_text.lower()
    
    # Build-related keywords
    build_keywords = ['building', 'shipped', 'launch', 'build', 'day', 'week', 'progress', 'shipping', 'code', 'dev', 'project', 'feature']
    motivational_keywords = ['motivation', 'start', 'begin', 'first', 'never', 'time', 'best time', 'yesterday', 'now']
    tech_keywords = ['react', 'vue', 'node', 'javascript', 'python', 'golang', 'rust', 'ai', 'agent', 'typescript', 'nextjs', 'tailwind']
    struggle_keywords = ['hard', 'difficult', 'struggle', 'stuck', 'problem', 'issue', 'bug', 'error', 'fix']
    launch_keywords = ['launch', 'release', 'live', 'product', 'shipped', 'shipping']
    hot_take_keywords = ['unpopular', 'controversial', 'hot take', 'opinion', 'change my mind', 'disagree', 'wrong']
    indie_hacker_keywords = ['indie', 'saas', 'mrr', 'revenue', 'bootstrapped', 'solo', 'founder']
    
    replies = []
    
    # Detect category and generate appropriate reply
    if any(kw in text_lower for kw in build_keywords):
        replies = [
            f"ship it 🚀",
            f"solid progress",
            f"day by day",
            f"consistency wins",
            f"keep building",
            f"nice work",
            f"forward motion",
            f"every commit counts"
        ]
    elif any(kw in text_lower for kw in hot_take_keywords):
        replies = [
            f"hot take and i agree",
            f"this is the way",
            f"unpopular but true",
            f"change my mind",
            f"facts don't care about feelings"
        ]
    elif any(kw in text_lower for kw in motivational_keywords):
        replies = [
            f"the best time is now",
            f"started is half done",
            f"let's gooo",
            f"no better day than today",
            f"action beats intention",
            f"tomorrow is not a strategy"
        ]
    elif any(kw in text_lower for kw in indie_hacker_keywords):
        replies = [
            f"bootstrapped vibes",
            f"indie hacker energy",
            f"saas life",
            f"solopreneur wins",
            f"build in public"
        ]
    elif any(kw in text_lower for kw in tech_keywords):
        replies = [
            f"clean stack",
            f"solid tech choice",
            f"tech decisions matter",
            f"nice stack",
            f"interesting choice",
            f"solid engineering"
        ]
    elif any(kw in text_lower for kw in struggle_keywords):
        replies = [
            f"every bug is a lesson",
            f"stuck means you're close",
            f"debugging builds character",
            f"keep pushing",
            f"the fix is near",
            f"you'll figure it out"
        ]
    elif any(kw in text_lower for kw in launch_keywords):
        replies = [
            f"congrats on the launch!",
            f"into the world it goes",
            f"live at last",
            f"well deserved 🎉",
            f"shipped! 🎉",
            f"live baby"
        ]
    else:
        # Generic but contextual replies
        replies = [
            f"this is the way",
            f"agreed",
            f"facts",
            f"well said",
            f"preach",
            f"solid point",
            f"true that",
            f"ngl this hits",
            f"real",
            f"couldn't agree more",
            f"exactly"
        ]
    
    # Add some variety based on tweet length
    if len(tweet_text) > 200:
        replies.append(f"detailed update. appreciate the transparency")
    if len(tweet_text) < 50:
        replies.append(f"short and sweet")
    
    return replies[:8]

@app.route('/')
def index():
    db = get_db()
    
    # Get pending tweets (not posted)
    pending_tweets = db.execute('''
        SELECT t.*, GROUP_CONCAT(r.content, '|||') as replies
        FROM tweets t
        LEFT JOIN replies r ON t.id = r.tweet_id AND r.status = 'pending'
        WHERE t.posted = 0
        GROUP BY t.id
        ORDER BY t.created_at DESC
    ''').fetchall()
    
    # Get posted tweets
    posted_tweets = db.execute('''
        SELECT * FROM tweets 
        WHERE posted = 1 
        ORDER BY posted_at DESC 
        LIMIT 20
    ''').fetchall()
    
    return render_template('index.html', pending=pending_tweets, posted=posted_tweets)

@app.route('/add', methods=['POST'])
def add_tweet():
    url = request.form.get('url')
    
    if not url:
        return redirect(url_for('index'))
    
    db = get_db()
    
    # Check if already exists
    existing = db.execute('SELECT id FROM tweets WHERE url = ?', (url,)).fetchone()
    if existing:
        return redirect(url_for('index'))
    
    # Auto-fetch tweet content
    tweet_data = fetch_tweet_content(url)
    
    # Insert tweet
    cursor = db.execute('INSERT INTO tweets (url, username, tweet_text) VALUES (?, ?, ?)', 
                        (url, tweet_data['username'], tweet_data['text']))
    tweet_id = cursor.lastrowid
    
    # Generate replies based on real content
    reply_options = generate_reply_content(tweet_data['text'], tweet_data['username'])
    for reply in reply_options:
        db.execute('INSERT INTO replies (tweet_id, content) VALUES (?, ?)', (tweet_id, reply))
    
    db.commit()
    return redirect(url_for('index'))

@app.route('/auto-add', methods=['POST'])
def auto_add():
    """Endpoint to auto-add tweets from external source"""
    data = request.get_json()
    urls = data.get('urls', [])
    
    db = get_db()
    added = []
    
    for url in urls:
        # Check if already exists
        existing = db.execute('SELECT id FROM tweets WHERE url = ?', (url,)).fetchone()
        if existing:
            continue
        
        # Fetch and process
        tweet_data = fetch_tweet_content(url)
        
        cursor = db.execute('INSERT INTO tweets (url, username, tweet_text) VALUES (?, ?, ?)', 
                            (url, tweet_data['username'], tweet_data['text']))
        tweet_id = cursor.lastrowid
        
        reply_options = generate_reply_content(tweet_data['text'], tweet_data['username'])
        for reply in reply_options:
            db.execute('INSERT INTO replies (tweet_id, content) VALUES (?, ?)', (tweet_id, reply))
        
        added.append(url)
    
    db.commit()
    return {'added': added}

@app.route('/post/<int:tweet_id>')
def mark_posted(tweet_id):
    db = get_db()
    db.execute('UPDATE tweets SET posted = 1, posted_at = CURRENT_TIMESTAMP WHERE id = ?', (tweet_id,))
    db.execute('UPDATE replies SET status = "posted" WHERE tweet_id = ?', (tweet_id,))
    db.commit()
    return redirect(url_for('index'))

@app.route('/feedback/<int:reply_id>', methods=['POST'])
def add_feedback(reply_id):
    action = request.form.get('action')  # like or dislike
    reason = request.form.get('reason', '')
    custom = request.form.get('custom', '')
    
    db = get_db()
    feedback = f"{action}:{reason}" if reason else action
    if custom:
        feedback += f" - {custom}"
    
    db.execute('UPDATE replies SET feedback = ?, status = ? WHERE id = ?', 
                (feedback, 'reviewed', reply_id))
    db.commit()
    return redirect(url_for('index'))

@app.route('/delete/<int:tweet_id>')
def delete_tweet(tweet_id):
    db = get_db()
    db.execute('DELETE FROM replies WHERE tweet_id = ?', (tweet_id,))
    db.execute('DELETE FROM tweets WHERE id = ?', (tweet_id,))
    db.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    # Bind to all interfaces for local network access
    app.run(host='0.0.0.0', port=5060, debug=True)
