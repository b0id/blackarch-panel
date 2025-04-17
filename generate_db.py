#!/usr/bin/env python3
"""
BlackArch Tool Metadata ETL Script
Extracts tool information from pacman and blackarch.org,
transforms the data, and loads it into a SQLite database.

This version includes progress reporting and incremental processing.
"""

import sqlite3
import subprocess
import re
import os
import time
import logging
import requests
from bs4 import BeautifulSoup

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='blackarch_etl.log'
)

# Database configuration
DB_FILE = 'blackarch_tools.db'

# Tracking variables for progress reporting
start_time = time.time()
total_tools_processed = 0

def execute_command(command):
    """Execute a shell command and return its output."""
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            check=True, 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8'
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        logging.error(f"Command execution failed: {command}\nError: {e.stderr}")
        print(f"Command failed: {command}")
        print(f"Error: {e.stderr}")
        return None

def init_database():
    """Initialize the SQLite database with required tables."""
    print("Initializing database...")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create tools table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tools (
        tool_name TEXT PRIMARY KEY NOT NULL,
        version TEXT NOT NULL,
        primary_category TEXT NOT NULL,
        short_description TEXT,
        long_description TEXT,
        upstream_url TEXT,
        help_command TEXT,
        last_updated INTEGER NOT NULL
    )
    ''')
    
    # Create dependencies table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS dependencies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tool_name TEXT NOT NULL,
        dependency_name TEXT NOT NULL,
        is_optional INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (tool_name) REFERENCES tools(tool_name)
    )
    ''')
    
    # Create tool_categories table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tool_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tool_name TEXT NOT NULL,
        category_name TEXT NOT NULL,
        FOREIGN KEY (tool_name) REFERENCES tools(tool_name)
    )
    ''')
    
    # Create indexes for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tools_primary_category ON tools(primary_category)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_dependencies_tool_name ON dependencies(tool_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tool_categories_tool_name ON tool_categories(tool_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tool_categories_category_name ON tool_categories(category_name)')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully.")

def extract_blackarch_tools():
    """Extract the list of all BlackArch tools using pacman."""
    print("Extracting BlackArch tools list...")
    output = execute_command("pacman -Sgg | grep blackarch | cut -d' ' -f2 | sort -u")
    if output:
        tools = [line.strip() for line in output.split('\n') if line.strip()]
        print(f"Found {len(tools)} BlackArch tools")
        return tools
    print("WARNING: No tools found! Check if BlackArch repository is configured.")
    return []

def extract_blackarch_categories():
    """Extract all BlackArch categories."""
    print("Extracting BlackArch categories...")
    output = execute_command("pacman -Sg | grep blackarch")
    if output:
        categories = [line.strip().split()[0] for line in output.split('\n') if line.strip()]
        print(f"Found {len(categories)} BlackArch categories")
        return categories
    print("WARNING: No categories found! Check if BlackArch repository is configured.")
    return []

def extract_tool_details(tool_name):
    """Extract detailed information about a tool using pacman -Si."""
    global total_tools_processed
    if total_tools_processed % 10 == 0:  # Report every 10 tools
        elapsed = time.time() - start_time
        print(f"Progress: Processed {total_tools_processed} tools in {elapsed:.1f} seconds")
    total_tools_processed += 1
    
    logging.info(f"Extracting details for tool: {tool_name}")
    output = execute_command(f"pacman -Si {tool_name}")
    if not output:
        print(f"Failed to extract details for: {tool_name}")
        return None
    
    # Parse the output to extract relevant fields
    details = {
        'tool_name': tool_name,
        'version': '',
        'description': '',
        'dependencies': [],
        'optdepends': [],
        'groups': []
    }
    
    # Simple parsing logic - would need to be refined based on actual output format
    current_field = None
    for line in output.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip().lower()
            value = value.strip()
            
            if key == 'version':
                details['version'] = value
            elif key == 'description':
                details['description'] = value
            elif key == 'depends on':
                current_field = 'dependencies'
                if value:
                    details['dependencies'] = [dep.strip() for dep in value.split() if dep.strip()]
            elif key == 'optional deps':
                current_field = 'optdepends'
                if value:
                    details['optdepends'] = [dep.strip() for dep in value.split() if dep.strip()]
            elif key == 'groups':
                current_field = 'groups'
                if value:
                    details['groups'] = [group.strip() for group in value.split() if group.strip()]
        elif current_field:
            # Continue parsing multi-line fields
            if current_field == 'dependencies':
                details['dependencies'].extend([dep.strip() for dep in line.split() if dep.strip()])
            elif current_field == 'optdepends':
                details['optdepends'].extend([dep.strip() for dep in line.split() if dep.strip()])
            elif current_field == 'groups':
                details['groups'].extend([group.strip() for group in line.split() if group.strip()])
    
    # Determine primary category
    primary_category = None
    for group in details.get('groups', []):
        if group.startswith('blackarch-'):
            primary_category = group
            break
    
    details['primary_category'] = primary_category or 'blackarch-uncategorized'
    
    return details

def scrape_tool_descriptions():
    """Scrape longer descriptions from blackarch.org website."""
    print("\nScraping tool descriptions from blackarch.org...")
    descriptions = {}
    
    # This is a simplified example - actual implementation would need to handle
    # navigating through category pages, error handling, etc.
    base_url = "https://blackarch.org"
    category_pages = [
        "/exploitation.html",
        "/scanner.html",
        "/webapp.html",
        "/fuzzer.html",
        "/recon.html"
        # Add more category pages as needed
    ]
    
    for page_url in category_pages:
        try:
            print(f"Scraping {base_url}{page_url}...")
            response = requests.get(f"{base_url}{page_url}")
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # This parsing logic would need to be adapted to the actual structure of the website
                # Assuming tools are in a table with class 'tbl'
                tool_tables = soup.find_all('table')
                for table in tool_tables:
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all('td')
                        if len(cells) >= 3:  # Assuming format: Name, Version, Description
                            tool_name = cells[0].text.strip()
                            description = cells[2].text.strip()
                            if tool_name and description:
                                descriptions[tool_name] = description
                                
                print(f"Found {len(descriptions)} tool descriptions so far")
            else:
                print(f"Failed to fetch {page_url}: Status code {response.status_code}")
        except Exception as e:
            print(f"Error scraping {page_url}: {str(e)}")
    
    print(f"Scraped descriptions for {len(descriptions)} tools total")
    return descriptions

def update_database(tools_data, scraped_descriptions):
    """Update the database with extracted and scraped tool data."""
    print(f"Updating database with {len(tools_data)} tools...")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Get current timestamp
    current_time = int(time.time())
    
    # Keep track of tools processed in this run
    processed_tools = set()
    tool_count = 0
    
    for tool_name, tool_data in tools_data.items():
        if not tool_data:
            continue
            
        processed_tools.add(tool_name)
        tool_count += 1
        
        # Generate a help command based on tool name
        help_command = f"{tool_name} --help || man {tool_name}"
        
        # Get the long description from scraped data if available, otherwise use short description
        long_description = scraped_descriptions.get(tool_name, tool_data.get('description', ''))
        
        # Check if tool already exists
        cursor.execute('SELECT tool_name FROM tools WHERE tool_name = ?', (tool_name,))
        exists = cursor.fetchone()
        
        if exists:
            # Update existing tool
            cursor.execute('''
            UPDATE tools SET 
                version = ?, 
                primary_category = ?, 
                short_description = ?, 
                long_description = ?, 
                help_command = ?, 
                last_updated = ?
            WHERE tool_name = ?
            ''', (
                tool_data.get('version', ''),
                tool_data.get('primary_category', 'blackarch-uncategorized'),
                tool_data.get('description', ''),
                long_description,
                help_command,
                current_time,
                tool_name
            ))
            
            # Remove old dependencies and categories
            cursor.execute('DELETE FROM dependencies WHERE tool_name = ?', (tool_name,))
            cursor.execute('DELETE FROM tool_categories WHERE tool_name = ?', (tool_name,))
        else:
            # Insert new tool
            cursor.execute('''
            INSERT INTO tools (
                tool_name, version, primary_category, short_description, 
                long_description, help_command, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                tool_name,
                tool_data.get('version', ''),
                tool_data.get('primary_category', 'blackarch-uncategorized'),
                tool_data.get('description', ''),
                long_description,
                help_command,
                current_time
            ))
        
        # Insert dependencies
        for dep in tool_data.get('dependencies', []):
            cursor.execute('''
            INSERT INTO dependencies (tool_name, dependency_name, is_optional)
            VALUES (?, ?, 0)
            ''', (tool_name, dep))
            
        for opt_dep in tool_data.get('optdepends', []):
            cursor.execute('''
            INSERT INTO dependencies (tool_name, dependency_name, is_optional)
            VALUES (?, ?, 1)
            ''', (tool_name, opt_dep))
        
        # Insert categories (primary and any additional)
        cursor.execute('''
        INSERT INTO tool_categories (tool_name, category_name)
        VALUES (?, ?)
        ''', (tool_name, tool_data.get('primary_category', 'blackarch-uncategorized')))
        
        # Add other categories from groups if they're blackarch-related but not the primary
        for group in tool_data.get('groups', []):
            if group.startswith('blackarch-') and group != tool_data.get('primary_category'):
                cursor.execute('''
                INSERT INTO tool_categories (tool_name, category_name)
                VALUES (?, ?)
                ''', (tool_name, group))
    
    conn.commit()
    conn.close()
    
    print(f"Database updated successfully. Added/updated {tool_count} tools.")

def quick_validation():
    """Perform a quick validation to confirm database is being created properly."""
    print("\n--- DATABASE VALIDATION ---")
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Database tables: {', '.join(tables)}")
        
        if not tables:
            print("ERROR: No tables created in database")
            return False
            
        # Check if we have tools
        cursor.execute("SELECT COUNT(*) FROM tools")
        tool_count = cursor.fetchone()[0]
        print(f"Database contains {tool_count} tools so far")
        
        # Check categories
        cursor.execute("SELECT COUNT(DISTINCT category_name) FROM tool_categories")
        category_count = cursor.fetchone()[0]
        print(f"Database contains {category_count} unique categories")
        
        # List a few tools as sample
        if tool_count > 0:
            cursor.execute("""
            SELECT t.tool_name, t.version, t.primary_category, t.short_description
            FROM tools t
            ORDER BY RANDOM()
            LIMIT 3
            """)
            print("\nSample tools:")
            for row in cursor.fetchall():
                print(f"  - {row[0]} (v{row[1]}) [{row[2]}]")
                print(f"    {row[3]}")
        
        # Check if we have dependencies
        cursor.execute("SELECT COUNT(*) FROM dependencies")
        dep_count = cursor.fetchone()[0]
        print(f"\nDependencies recorded: {dep_count}")
        
        conn.close()
        return tool_count > 0
    except sqlite3.Error as e:
        print(f"Database validation error: {e}")
        return False

def main():
    global start_time
    print("Starting BlackArch Tools ETL process...")
    start_time = time.time()
    
    # Initialize the database
    init_database()
    
    # Extract tool list
    tools_list = extract_blackarch_tools()
    if not tools_list:
        print("No tools found. Exiting.")
        return
        
    total_tools = len(tools_list)
    
    # Get categories list for reference
    categories = extract_blackarch_categories()
    print(f"Available categories: {', '.join(categories)}")
    
    # Process in batches of 50
    batch_size = 50
    for i in range(0, total_tools, batch_size):
        batch = tools_list[i:i+batch_size]
        batch_num = i//batch_size + 1
        total_batches = (total_tools+batch_size-1)//batch_size
        print(f"\n=== Processing batch {batch_num}/{total_batches} (tools {i+1}-{min(i+batch_size, total_tools)}) ===")
        
        # Extract details for this batch
        tools_data = {}
        for tool_name in batch:
            details = extract_tool_details(tool_name)
            if details:
                tools_data[tool_name] = details
        
        # Scrape additional descriptions (only in first batch to save time)
        scraped_descriptions = {}
        if i == 0:
            scraped_descriptions = scrape_tool_descriptions()
        
        # Update the database with this batch
        update_database(tools_data, scraped_descriptions)
        
        # Validate after each batch
        is_valid = quick_validation()
        if not is_valid:
            print("WARNING: Database validation failed. You may want to check for issues.")
        
        elapsed = time.time() - start_time
        tools_per_second = (i + len(batch)) / elapsed if elapsed > 0 else 0
        print(f"\nProgress: {min(i+batch_size, total_tools)}/{total_tools} tools processed ({tools_per_second:.1f} tools/sec)")
        estimated_remaining = (total_tools - (i + len(batch))) / tools_per_second if tools_per_second > 0 else 0
        print(f"Estimated time remaining: {estimated_remaining/60:.1f} minutes")
        
        print("\nYou can press Ctrl+C to stop processing now if you want to check the database.")
        
        # You can uncomment this to pause between batches
        # input("Press Enter to continue to next batch...")
        
    print("\nETL process completed successfully")
    
    # Final validation
    quick_validation()
    
    total_time = time.time() - start_time
    print(f"\nTotal processing time: {total_time/60:.1f} minutes")
    print(f"Tools processed: {total_tools}")
    print(f"Average speed: {total_tools/total_time:.1f} tools/second")
    print(f"\nYou can now browse the database using the bapanel.py script or SQLite directly")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user.")
        print("The database will contain all tools processed so far.")
        print("You can still browse what has been collected.")
        quick_validation()