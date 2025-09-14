import requests
import sqlite3
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
import uvicorn

DB_FILE = "textures.db"
BASE_URL = "https://ambientcg.com/list"

# --- دیتابیس ---
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS textures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    url TEXT UNIQUE
)
""")
conn.commit()

# --- کرول ساده ---
def crawl_ambientcg():
    print("[+] Crawling ambientCG ...")
    try:
        r = requests.get(BASE_URL)
        soup = BeautifulSoup(r.text, "html.parser")

        items = soup.select(".Card")
        for item in items:
            title_tag = item.select_one(".CardTitle")
            if title_tag:
                title = title_tag.get_text(strip=True)
                link = item.get('href')
                if link:
                    full_link = "https://ambientcg.com" + link
                    try:
                        cursor.execute("INSERT INTO textures (title, url) VALUES (?, ?)", (title, full_link))
                    except sqlite3.IntegrityError:
                        continue  # skip duplicates
        conn.commit()
        print("[+] Crawling done.")
    except Exception as e:
        print("[!] Crawling failed:", e)

# --- FastAPI ---
app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def search(q: str = Query("", description="Search keyword")):
    if q:
        cursor.execute("SELECT title, url FROM textures WHERE title LIKE ?", (f"%{q}%",))
    else:
        cursor.execute("SELECT title, url FROM textures LIMIT 20")
    rows = cursor.fetchall()

    html = "<h2>Texture Search</h2>"
    html += "<form><input name='q' placeholder='Search...' value='{}'><input type='submit' value='Search'></form>".format(q)
    html += "<ul>"
    for title, url in rows:
        html += f"<li><a href='{url}' target='_blank'>{title}</a></li>"
    html += "</ul>"
    return html

if __name__ == "__main__":
    crawl_ambientcg()
    uvicorn.run(app, host="0.0.0.0", port=10000)
