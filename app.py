import sqlite3
import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from bs4 import BeautifulSoup
import re
from typing import Optional

# Database configuration
DATABASE_FILE = "textures.db"
# Source to crawl
SOURCE_URL = "https://ambientcg.com/list"

def setup_database():
    """Initializes the SQLite database and table."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS textures (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE
        )
    """)
    conn.commit()
    conn.close()

def crawl_and_index():
    """Crawls the source URL and populates the database."""
    print("Crawling and indexing resources from AmbientCG...")
    try:
        # Added a timeout of 30 seconds to prevent hanging
        response = requests.get(SOURCE_URL, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # Find all list items, which are <a> tags with class "list-item"
        items = soup.find_all('a', class_='list-item')
        
        count = 0
        for item in items:
            # Extract the URL from the href attribute
            url = f"https://ambientcg.com{item.get('href')}"
            
            # Extract the title from the inner <div>
            title_div = item.find('div', class_='list-item-title')
            title = title_div.get_text(strip=True) if title_div else "Untitled"
            
            # Insert or ignore duplicates based on the unique URL constraint
            try:
                cursor.execute("INSERT INTO textures (title, url) VALUES (?, ?)", (title, url))
                count += 1
            except sqlite3.IntegrityError:
                # This means the URL already exists, so we skip it.
                pass
        
        conn.commit()
        conn.close()
        print(f"Indexing complete. Added {count} new entries.")

    except requests.exceptions.RequestException as e:
        print(f"Error during crawling: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events.
    The database setup and crawling logic is triggered on startup.
    """
    setup_database()
    crawl_and_index()
    yield
    # You can add cleanup code here if needed.

# Initialize FastAPI app with the lifespan handler
app = FastAPI(lifespan=lifespan)

# Main route for the search form and results
@app.get("/", response_class=HTMLResponse)
async def home(request: Request, q: Optional[str] = None):
    """
    Handles the search functionality and displays results.
    - If a search query 'q' is provided, it searches the database.
    - Otherwise, it displays the first 20 entries.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # Determine which query to run based on the search term
    if q:
        # Sanitize the input to prevent SQL injection (although the `?` placeholder does this)
        sanitized_q = f'%{q}%'
        cursor.execute("SELECT title, url FROM textures WHERE title LIKE ? LIMIT 50", (sanitized_q,))
        results = cursor.fetchall()
        title = f"Search Results for '{q}'"
        
        if not results:
            results_html = "<p class='text-gray-500 mt-4'>No results found.</p>"
        else:
            results_html = "<ul class='list-disc pl-5 mt-4 space-y-2'>"
            for title, url in results:
                results_html += f"<li><a href='{url}' target='_blank' class='text-blue-500 hover:underline'>{title}</a></li>"
            results_html += "</ul>"
            
    else:
        # If no query, show the first 20 entries
        cursor.execute("SELECT title, url FROM textures LIMIT 20")
        results = cursor.fetchall()
        title = "Featured Resources"
        
        results_html = "<ul class='list-disc pl-5 mt-4 space-y-2'>"
        for title, url in results:
            results_html += f"<li><a href='{url}' target='_blank' class='text-blue-500 hover:underline'>{title}</a></li>"
        results_html += "</ul>"
        
    conn.close()
    
    # Basic HTML template for the page with TailwindCSS classes
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Texture Search Engine</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap" rel="stylesheet">
        <style>
            body {{
                font-family: 'Inter', sans-serif;
                background-color: #f3f4f6;
            }}
        </style>
    </head>
    <body class="bg-gray-100 flex items-center justify-center min-h-screen p-4">
        <div class="bg-white rounded-xl shadow-lg p-8 w-full max-w-2xl">
            <h1 class="text-3xl font-bold text-gray-800 mb-6 text-center">Design Resource Search</h1>
            <form action="/" method="get" class="flex flex-col sm:flex-row gap-4 mb-8">
                <input type="text" name="q" placeholder="Search for textures, materials..." class="flex-1 p-3 rounded-lg border-2 border-gray-300 focus:outline-none focus:border-blue-500 transition-colors" value="{q if q else ''}">
                <button type="submit" class="bg-blue-600 text-white font-semibold py-3 px-6 rounded-lg hover:bg-blue-700 transition-colors shadow-md">Search</button>
            </form>
            <h2 class="text-2xl font-semibold text-gray-700 mb-4">{title}</h2>
            {results_html}
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/status")
async def status():
    """
    A simple status page to check if the database has been populated.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM textures")
    count = cursor.fetchone()[0]
    conn.close()
    return {"status": "ok", "indexed_entries": count}

# To run this app locally, you can use the command:
# uvicorn app:app --reload