import sqlite3
import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from bs4 import BeautifulSoup
from typing import Optional

# Database configuration
DATABASE_FILE = "textures.db"

# List of sources to crawl with specific selectors
SOURCES = [
    {
        "url": "https://ambientcg.com/list",
        "name": "AmbientCG",
        "selector": 'a.AssetBrowser_assetListItem__f5L0f',
        "get_title": lambda item: item.find('h3').get_text(strip=True),
        "get_url": lambda item: f"https://ambientcg.com{item.get('href')}"
    },
    {
        "url": "https://polyhaven.com/textures",
        "name": "Poly Haven",
        "selector": 'a.tile',
        "get_title": lambda item: item.find('h2').get_text(strip=True),
        "get_url": lambda item: f"https://polyhaven.com{item.get('href')}"
    },
    {
        "url": "https://www.textures.com/browse/pbr-materials/114511",
        "name": "Textures.com (PBR)",
        "selector": 'div.list-item > a',
        "get_title": lambda item: item.get('title'),
        "get_url": lambda item: f"https://www.textures.com{item.get('href')}"
    }
]

def setup_database():
    """Initializes the SQLite database and table."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS textures (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            source TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def crawl_and_index_all_sources():
    """Crawls all defined sources and populates the database with detailed logging."""
    print("Starting the crawling and indexing process for all sources...")
    
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    total_added = 0
    for source in SOURCES:
        url = source['url']
        source_name = source['name']
        selector = source['selector']
        get_title = source['get_title']
        get_url = source['get_url']
        
        print(f"\n--- Crawling {source_name} ---")
        try:
            print(f"Attempting to fetch data from: {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            print(f"Successfully fetched data. HTTP status code: {response.status_code}")
            
            soup = BeautifulSoup(response.content, 'html.parser')
            items = soup.select(selector)
            
            print(f"Found {len(items)} items on the page.")
            
            count = 0
            for item in items:
                try:
                    title = get_title(item)
                    item_url = get_url(item)
                    
                    if title and item_url and item_url.startswith('http'):
                        cursor.execute(
                            "INSERT OR IGNORE INTO textures (title, url, source) VALUES (?, ?, ?)", 
                            (title, item_url, source_name)
                        )
                        count += 1
                except Exception as e:
                    print(f"Failed to process an item from {source_name}: {e}")
            
            conn.commit()
            total_added += count
            print(f"Indexing complete for {source_name}. Added {count} new entries.")

        except requests.exceptions.RequestException as e:
            print(f"Error during crawling {source_name}: A network-related issue occurred. Details: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during crawling {source_name}: {e}")

    conn.close()
    print(f"\nTotal indexing complete. Added {total_added} new entries across all sources.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events.
    The database setup and crawling logic is triggered on startup.
    """
    setup_database()
    crawl_and_index_all_sources()
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
        sanitized_q = f'%{q}%'
        cursor.execute("SELECT title, url, source FROM textures WHERE title LIKE ? LIMIT 50", (sanitized_q,))
        results = cursor.fetchall()
        title = f"Search Results for '{q}'"
        
        if not results:
            results_html = "<p class='text-gray-500 mt-4'>No results found.</p>"
        else:
            results_html = "<ul class='list-disc pl-5 mt-4 space-y-2'>"
            for result_title, url, source in results:
                results_html += f"<li><a href='{url}' target='_blank' class='text-blue-500 hover:underline'>{result_title}</a> <span class='text-xs text-gray-500'>({source})</span></li>"
            results_html += "</ul>"
            
    else:
        cursor.execute("SELECT title, url, source FROM textures LIMIT 50")
        results = cursor.fetchall()
        title = "Featured Resources"
        
        results_html = "<ul class='list-disc pl-5 mt-4 space-y-2'>"
        for result_title, url, source in results:
            results_html += f"<li><a href='{url}' target='_blank' class='text-blue-500 hover:underline'>{result_title}</a> <span class='text-xs text-gray-500'>({source})</span></li>"
        results_html += "</ul>"
        
    conn.close()
    
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
