#!/usr/bin/env python3
"""
BlackArch Panel - CLI Tool for browsing BlackArch tools metadata
"""

import os
import sys
import sqlite3
import subprocess
import argparse
import json
import time
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich.markdown import Markdown

# Configuration
DB_FILE = 'blackarch_tools.db'
console = Console()

def check_database():
    """Check if the database file exists and is accessible."""
    if not os.path.exists(DB_FILE):
        console.print(f"[bold red]Error:[/bold red] Database file '{DB_FILE}' not found.")
        console.print("Please run the data extraction script first or ensure the database file is in the correct location.")
        sys.exit(1)

def get_connection():
    """Get a connection to the SQLite database."""
    try:
        return sqlite3.connect(DB_FILE)
    except sqlite3.Error as e:
        console.print(f"[bold red]Database error:[/bold red] {e}")
        sys.exit(1)

def list_categories():
    """Display a list of all BlackArch tool categories."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT DISTINCT category_name, COUNT(tool_name) as tool_count 
    FROM tool_categories 
    GROUP BY category_name 
    ORDER BY category_name
    ''')
    
    categories = cursor.fetchall()
    conn.close()
    
    if not categories:
        console.print("[yellow]No categories found in the database.[/yellow]")
        return None
    
    table = Table(title="BlackArch Tool Categories")
    table.add_column("#", style="cyan")
    table.add_column("Category", style="green")
    table.add_column("Tool Count", justify="right", style="magenta")
    
    for i, (category, count) in enumerate(categories, 1):
        table.add_row(str(i), category, str(count))
    
    console.print(table)
    return categories

def list_tools_in_category(category):
    """Display a list of tools in the specified category."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT t.tool_name, t.short_description, t.version
    FROM tools t
    JOIN tool_categories tc ON t.tool_name = tc.tool_name
    WHERE tc.category_name = ?
    ORDER BY t.tool_name
    ''', (category,))
    
    tools = cursor.fetchall()
    conn.close()
    
    if not tools:
        console.print(f"[yellow]No tools found in category: {category}[/yellow]")
        return None
    
    table = Table(title=f"Tools in {category}")
    table.add_column("#", style="cyan")
    table.add_column("Tool", style="green")
    table.add_column("Version", style="blue")
    table.add_column("Description", style="yellow")
    
    for i, (name, desc, version) in enumerate(tools, 1):
        table.add_row(str(i), name, version, desc or "No description available")
    
    console.print(table)
    return tools

def list_all_tools(page=1, per_page=20):
    """Display a paginated list of all tools."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get total count first
    cursor.execute('SELECT COUNT(*) FROM tools')
    total = cursor.fetchone()[0]
    
    offset = (page - 1) * per_page
    
    cursor.execute('''
    SELECT tool_name, short_description, version, primary_category
    FROM tools
    ORDER BY tool_name
    LIMIT ? OFFSET ?
    ''', (per_page, offset))
    
    tools = cursor.fetchall()
    conn.close()
    
    if not tools:
        if page > 1:
            console.print("[yellow]No more tools to display.[/yellow]")
        else:
            console.print("[yellow]No tools found in the database.[/yellow]")
        return None
    
    total_pages = (total + per_page - 1) // per_page  # Ceiling division
    
    table = Table(title=f"All BlackArch Tools (Page {page}/{total_pages})")
    table.add_column("#", style="cyan")
    table.add_column("Tool", style="green")
    table.add_column("Version", style="blue")
    table.add_column("Category", style="magenta")
    table.add_column("Description", style="yellow")
    
    for i, (name, desc, version, category) in enumerate(tools, offset + 1):
        table.add_row(str(i), name, version, category.replace('blackarch-', ''), desc or "No description available")
    
    console.print(table)
    
    # Return both the tools list and pagination info
    return {
        'tools': tools,
        'page': page,
        'total_pages': total_pages,
        'per_page': per_page
    }

def search_tools(term):
    """Search for tools by name or description."""
    search_term = f"%{term}%"
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT tool_name, short_description, version, primary_category
    FROM tools
    WHERE tool_name LIKE ? OR short_description LIKE ? OR long_description LIKE ?
    ORDER BY tool_name
    ''', (search_term, search_term, search_term))
    
    tools = cursor.fetchall()
    conn.close()
    
    if not tools:
        console.print(f"[yellow]No tools found matching: {term}[/yellow]")
        return None
    
    table = Table(title=f"Search Results for '{term}'")
    table.add_column("#", style="cyan")
    table.add_column("Tool", style="green")
    table.add_column("Version", style="blue")
    table.add_column("Category", style="magenta")
    table.add_column("Description", style="yellow")
    
    for i, (name, desc, version, category) in enumerate(tools, 1):
        table.add_row(str(i), name, version, category.replace('blackarch-', ''), desc or "No description available")
    
    console.print(table)
    return tools

def show_tool_details(tool_name):
    """Display detailed information about a specific tool."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get basic tool info
    cursor.execute('SELECT * FROM tools WHERE tool_name = ?', (tool_name,))
    tool = cursor.fetchone()
    
    if not tool:
        console.print(f"[bold red]Tool not found:[/bold red] {tool_name}")
        conn.close()
        return
    
    # Get column names
    column_names = [description[0] for description in cursor.description]
    tool_dict = {column_names[i]: tool[i] for i in range(len(column_names))}
    
    # Get dependencies
    cursor.execute('''
    SELECT dependency_name, is_optional
    FROM dependencies
    WHERE tool_name = ?
    ORDER BY is_optional, dependency_name
    ''', (tool_name,))
    dependencies = cursor.fetchall()
    
    # Get all categories
    cursor.execute('''
    SELECT category_name
    FROM tool_categories
    WHERE tool_name = ?
    ORDER BY category_name
    ''', (tool_name,))
    categories = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    
    # Display tool details in a panel
    title = Text(f"{tool_dict['tool_name']} (v{tool_dict['version']})", style="bold green")
    
    details = []
    details.append(Text("DESCRIPTION", style="bold yellow"))
    details.append(Text(tool_dict['long_description'] or tool_dict['short_description'] or "No description available"))
    details.append(Text(""))  # Changed from "" to Text("")
    
    details.append(Text("CATEGORIES", style="bold yellow"))
    for category in categories:
        details.append(Text(f"• {category}"))
    details.append(Text(""))  # Changed from "" to Text("")
    
    if dependencies:
        details.append(Text("DEPENDENCIES", style="bold yellow"))
        for dep, is_optional in dependencies:
            if is_optional:
                details.append(Text(f"• {dep} (optional)", style="dim"))
            else:
                details.append(Text(f"• {dep}"))
        details.append(Text(""))  # Changed from "" to Text("")
    
    if tool_dict.get('upstream_url'):
        details.append(Text("UPSTREAM URL", style="bold yellow"))
        details.append(Text(tool_dict['upstream_url']))
        details.append(Text(""))  # Changed from "" to Text("")
    
    details.append(Text("LAST UPDATED", style="bold yellow"))
    details.append(Text(f"{tool_dict['last_updated']} (Unix timestamp)"))
    
    panel_content = Text("\n").join(details)
    panel = Panel(panel_content, title=title, expand=False)
    
    console.print(panel)
    
    # Show related tools
    related = find_related_tools(tool_name)
    if related:
        console.print("\n[bold cyan]Related Tools:[/bold cyan]")
        related_table = Table(show_header=False, box=None)
        related_table.add_column("", style="green")
        related_table.add_column("", style="yellow")
        
        for name, desc, _ in related:
            desc_short = desc[:60] + "..." if desc and len(desc) > 60 else desc
            related_table.add_row(f"• {name}", desc_short or "No description")
        
        console.print(related_table)
    
    script_choice = Prompt.ask(
        "Press 'g' to generate a script wrapper for this tool, any other key to continue",
        default=""
    )
    if script_choice.lower() == 'g':
        generate_tool_script(tool_name)
    
    return tool_dict

def execute_help_command(help_command):
    """Execute the help command for a tool and display the output."""
    console.print(f"[bold blue]Executing:[/bold blue] {help_command}")
    console.print("")
    
    try:
        result = subprocess.run(
            help_command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8'
        )
        
        if result.stdout:
            console.print(result.stdout)
        if result.stderr:
            console.print(f"[red]{result.stderr}[/red]")
            
        if not result.stdout and not result.stderr:
            console.print("[yellow]No output from help command.[/yellow]")
    
    except Exception as e:
        console.print(f"[bold red]Error executing help command:[/bold red] {str(e)}")

def interactive_mode():
    """Run the application in interactive mode."""
    check_database()
    
    while True:
        console.print("\n[bold cyan]BlackArch Panel - Interactive Mode[/bold cyan]")
        console.print("1. List categories")
        console.print("2. List all tools")
        console.print("3. Search tools")
        console.print("4. Show random tool")
        console.print("5. Export database to JSON")
        console.print("6. Import from JSON")
        console.print("q. Quit")
        
        choice = Prompt.ask("Select an option", choices=["1", "2", "3", "4", "5", "6", "q"], default="1")
        
        if choice == "q":
            break
        
        elif choice == "1":
            categories = list_categories()
            if categories:
                cat_choice = Prompt.ask(
                    "Enter category number or 'b' to go back",
                    default="b"
                )
                if cat_choice.lower() != 'b':
                    try:
                        idx = int(cat_choice) - 1
                        if 0 <= idx < len(categories):
                            category = categories[idx][0]
                            tools = list_tools_in_category(category)
                            
                            if tools:
                                tool_choice = Prompt.ask(
                                    "Enter tool number, 'b' to go back, or 'q' to quit",
                                    default="b"
                                )
                                if tool_choice.lower() == 'q':
                                    break
                                elif tool_choice.lower() != 'b':
                                    try:
                                        tool_idx = int(tool_choice) - 1
                                        if 0 <= tool_idx < len(tools):
                                            tool_name = tools[tool_idx][0]
                                            tool_data = show_tool_details(tool_name)
                                            
                                            if tool_data:
                                                help_choice = Prompt.ask(
                                                    "Press 'h' to view help/parameters, any other key to continue",
                                                    default=""
                                                )
                                                if help_choice.lower() == 'h':
                                                    execute_help_command(tool_data['help_command'])
                                    except ValueError:
                                        console.print("[red]Invalid tool number.[/red]")
                        else:
                            console.print("[red]Invalid category number.[/red]")
                    except ValueError:
                        console.print("[red]Invalid input. Please enter a number.[/red]")
        
        elif choice == "2":
            page = 1
            per_page = 20
            while True:
                result = list_all_tools(page, per_page)
                if not result:
                    break
                
                tools = result['tools']
                total_pages = result['total_pages']
                
                nav_prompt = "Enter tool number, 'n' for next page, 'p' for previous page, 'b' to go back, or 'q' to quit"
                if page >= total_pages:
                    nav_prompt = nav_prompt.replace("'n' for next page, ", "")
                if page <= 1:
                    nav_prompt = nav_prompt.replace("'p' for previous page, ", "")
                
                tool_choice = Prompt.ask(nav_prompt, default="b")
                
                if tool_choice.lower() == 'q':
                    return
                elif tool_choice.lower() == 'b':
                    break
                elif tool_choice.lower() == 'n' and page < total_pages:
                    page += 1
                elif tool_choice.lower() == 'p' and page > 1:
                    page -= 1
                else:
                    try:
                        tool_idx = int(tool_choice) - 1 - ((page - 1) * per_page)
                        if 0 <= tool_idx < len(tools):
                            tool_name = tools[tool_idx][0]
                            tool_data = show_tool_details(tool_name)
                            
                            if tool_data:
                                help_choice = Prompt.ask(
                                    "Press 'h' to view help/parameters, any other key to continue",
                                    default=""
                                )
                                if help_choice.lower() == 'h':
                                    execute_help_command(tool_data['help_command'])
                        else:
                            console.print("[red]Invalid tool number.[/red]")
                    except ValueError:
                        pass  # Handled by the navigation options
        
        elif choice == "3":
            search_term = Prompt.ask("Enter search term")
            tools = search_tools(search_term)
            
            if tools:
                tool_choice = Prompt.ask(
                    "Enter tool number, 'b' to go back, or 'q' to quit",
                    default="b"
                )
                if tool_choice.lower() == 'q':
                    break
                elif tool_choice.lower() != 'b':
                    try:
                        tool_idx = int(tool_choice) - 1
                        if 0 <= tool_idx < len(tools):
                            tool_name = tools[tool_idx][0]
                            tool_data = show_tool_details(tool_name)
                            
                            if tool_data:
                                help_choice = Prompt.ask(
                                    "Press 'h' to view help/parameters, any other key to continue",
                                    default=""
                                )
                                if help_choice.lower() == 'h':
                                    execute_help_command(tool_data['help_command'])
                        else:
                            console.print("[red]Invalid tool number.[/red]")
                    except ValueError:
                        console.print("[red]Invalid input. Please enter a number.[/red]")
        
        elif choice == "4":
            tool_data = show_random_tool()
            if tool_data:
                help_choice = Prompt.ask(
                    "Press 'h' to view help/parameters, any other key to continue",
                    default=""
                )
                if help_choice.lower() == 'h':
                    execute_help_command(tool_data['help_command'])
                    
        elif choice == "5":
            console.print("\n[bold cyan]Export Options[/bold cyan]")
            console.print("1. Export all tools")
            console.print("2. Export tools by category")
            console.print("3. Export tools by search")
            console.print("4. Export current view/selection")
            console.print("b. Back")
            
            export_choice = Prompt.ask("Select an export option", choices=["1", "2", "3", "4", "b"], default="1")
            
            if export_choice == "b":
                continue
                
            output_file = Prompt.ask("Enter output filename", default="blackarch_tools.json")
            
            if export_choice == "1":
                # Export all
                export_tools_to_json(output_file)
            elif export_choice == "2":
                # Export by category
                categories = list_categories()
                if categories:
                    cat_choice = Prompt.ask(
                        "Enter category number or 'b' to cancel",
                        default="b"
                    )
                    if cat_choice.lower() != 'b':
                        try:
                            idx = int(cat_choice) - 1
                            if 0 <= idx < len(categories):
                                category = categories[idx][0]
                                export_tools_to_json(output_file, 'category', category)
                            else:
                                console.print("[red]Invalid category number.[/red]")
                        except ValueError:
                            console.print("[red]Invalid input. Please enter a number.[/red]")
            elif export_choice == "3":
                # Export by search
                search_term = Prompt.ask("Enter search term")
                export_tools_to_json(output_file, 'search', search_term)
            elif export_choice == "4":
                # This option needs context from the current view
                console.print("[yellow]Please use the search or category view to select tools first.[/yellow]")
                    
        elif choice == "6":
            input_file = Prompt.ask("Enter JSON filename to import", default="blackarch_tools.json")
            import_from_json(input_file)

def export_tools_to_json(output_file, filter_type=None, filter_value=None):
    """Export tools to a JSON file with filtering options.
    
    Args:
        output_file: The filename for the JSON output
        filter_type: The type of filter ('category', 'search', 'tools')
        filter_value: The value to filter by (category name, search term, or list of tool names)
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Base query
    base_query = 'SELECT DISTINCT t.* FROM tools t'
    params = []
    
    # Apply filters
    if filter_type == 'category':
        base_query += ' JOIN tool_categories tc ON t.tool_name = tc.tool_name WHERE tc.category_name = ?'
        params = [filter_value]
        filter_desc = f"in category '{filter_value}'"
    elif filter_type == 'search':
        search_term = f"%{filter_value}%"
        base_query += ' WHERE t.tool_name LIKE ? OR t.short_description LIKE ? OR t.long_description LIKE ?'
        params = [search_term, search_term, search_term]
        filter_desc = f"matching search '{filter_value}'"
    elif filter_type == 'tools' and isinstance(filter_value, list) and filter_value:
        placeholders = ','.join('?' * len(filter_value))
        base_query += f' WHERE t.tool_name IN ({placeholders})'
        params = filter_value
        filter_desc = f"selected ({len(filter_value)} tools)"
    else:
        filter_desc = "all"
    
    # Execute query
    cursor.execute(base_query, params)
    tools = [dict(row) for row in cursor.fetchall()]

    # For each tool, get dependencies and categories
    for tool in tools:
        cursor.execute('SELECT dependency_name, is_optional FROM dependencies WHERE tool_name = ?', 
                      (tool['tool_name'],))
        tool['dependencies'] = [
            {'name': row[0], 'optional': bool(row[1])} 
            for row in cursor.fetchall()
        ]
        
        cursor.execute('SELECT category_name FROM tool_categories WHERE tool_name = ?', 
                      (tool['tool_name'],))
        tool['categories'] = [row[0] for row in cursor.fetchall()]

    conn.close()

    # Write to JSON file
    with open(output_file, 'w') as f:
        json.dump({
            'tools': tools, 
            'exported_at': int(time.time()),
            'filter': {
                'type': filter_type,
                'value': filter_value if not isinstance(filter_value, list) else f"{len(filter_value)} tools"
            }
        }, f, indent=2)

    console.print(f"[green]Exported {len(tools)} {filter_desc} tools to {output_file}[/green]")
    return output_file

def find_related_tools(tool_name):
    """Find tools related to the given tool based on categories."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get categories for the tool
    cursor.execute('''
    SELECT category_name FROM tool_categories WHERE tool_name = ?
    ''', (tool_name,))
    categories = [row[0] for row in cursor.fetchall()]
    
    if not categories:
        conn.close()
        return []
    
    # Find tools that share categories
    placeholders = ','.join(['?'] * len(categories))
    cursor.execute(f'''
    SELECT tc.tool_name, t.short_description, COUNT(tc.category_name) as common_categories
    FROM tool_categories tc
    JOIN tools t ON tc.tool_name = t.tool_name
    WHERE tc.category_name IN ({placeholders})
    AND tc.tool_name != ?
    GROUP BY tc.tool_name
    ORDER BY common_categories DESC
    LIMIT 5
    ''', categories + [tool_name])
    
    related_tools = cursor.fetchall()
    conn.close()
    
    return related_tools

def show_random_tool():
    """Display information about a randomly selected tool."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT tool_name FROM tools ORDER BY RANDOM() LIMIT 1')
    result = cursor.fetchone()
    conn.close()
    
    if result:
        tool_name = result[0]
        console.print(f"\n[bold cyan]Randomly selected tool:[/bold cyan] {tool_name}")
        return show_tool_details(tool_name)
    else:
        console.print("[yellow]No tools found in the database.[/yellow]")
        return None

def generate_tool_script(tool_name):
    """Generate a simple bash script wrapper for a tool with common options."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM tools WHERE tool_name = ?', (tool_name,))
    tool = cursor.fetchone()
    
    if not tool:
        console.print(f"[bold red]Tool not found:[/bold red] {tool_name}")
        conn.close()
        return
    
    # Get column names
    column_names = [description[0] for description in cursor.description]
    tool_dict = {column_names[i]: tool[i] for i in range(len(column_names))}
    
    # Get dependencies
    cursor.execute('''
    SELECT dependency_name FROM dependencies
    WHERE tool_name = ? AND is_optional = 0
    ORDER BY dependency_name
    ''', (tool_name,))
    dependencies = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    
    # Create a simple script
    script = f"""#!/bin/bash
# Wrapper script for {tool_name} [BETA]
# Description: {tool_dict['short_description']}
# Generated by BlackArch Panel

# Colors for output
RED="\\033[0;31m"
GREEN="\\033[0;32m"
YELLOW="\\033[1;33m"
BLUE="\\033[0;34m"
NC="\\033[0m" # No Color

echo -e "${{BLUE}}=== {tool_name} Wrapper [BETA] ===${{NC}}"
echo -e "${{YELLOW}}Description:${{NC}} {tool_dict['short_description']}"

# Check if tool is installed
if ! command -v {tool_name} &> /dev/null; then
    echo -e "${{RED}}Error:${{NC}} {tool_name} is not installed"
    echo -e "${{YELLOW}}To install:${{NC}} sudo pacman -S {tool_name}"
    exit 1
fi

# Check dependencies
"""
    
    # Add dependency checks
    for dep in dependencies:
        script += f"""
if ! command -v {dep} &> /dev/null && ! pacman -Q {dep} &> /dev/null; then
    echo -e "${{YELLOW}}Warning:${{NC}} Dependency '{dep}' may not be installed"
fi
"""
    
    # Add help section
    script += f"""
# Display help information
if [ "$1" == "-h" ] || [ "$1" == "--help" ] || [ -z "$1" ]; then
    echo -e "${{BLUE}}Usage:${{NC}} $0 [options]"
    echo ""
    echo -e "${{YELLOW}}This is a wrapper script for {tool_name}.${{NC}}"
    echo "For complete help, see: {tool_dict['help_command']}"
    echo ""
    echo -e "${{BLUE}}Common usage examples:${{NC}}"
    echo "  $0 --basic     # Run with basic options"
    echo "  $0 --thorough  # Run with thorough options"
    echo ""
    echo -e "${{BLUE}}Or pass through original options:${{NC}}"
    echo "  $0 -- [original {tool_name} options]"
    echo ""
    exit 0
fi

# Handle script-specific options
if [ "$1" == "--basic" ]; then
    echo -e "${{GREEN}}Running {tool_name} with basic options...${{NC}}"
    {tool_name} --help | head -n 5
    # Add actual basic command for the specific tool
    # {tool_name} [basic options]
    exit 0
elif [ "$1" == "--thorough" ]; then
    echo -e "${{GREEN}}Running {tool_name} with thorough options...${{NC}}"
    # Add actual thorough command for the specific tool
    # {tool_name} [thorough options]
    exit 0
elif [ "$1" == "--" ]; then
    shift
    echo -e "${{GREEN}}Running {tool_name} with custom options...${{NC}}"
    {tool_name} "$@"
else:
    echo -e "${{GREEN}}Running {tool_name} with provided options...${{NC}}"
    {tool_name} "$@"
fi
"""
    
    script_file = f"{tool_name}_wrapper.sh"
    with open(script_file, 'w') as f:
        f.write(script)
    
    os.chmod(script_file, 0o755)  # Make executable
    
    console.print(f"[green]Script created:[/green] {script_file}")
    console.print("[yellow]Note: This is a BETA feature. The generated script is a template and may need customization.[/yellow]")
    return script_file

def import_from_json(json_file='blackarch_tools.json'):
    """Import tool data from a JSON file."""
    try:
        console.print(f"Importing tools from {json_file}...")
        with open(json_file, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        console.print(f"[bold red]Error loading JSON file:[/bold red] {e}")
        return False
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Begin transaction
    conn.execute('BEGIN TRANSACTION')
    
    try:
        tool_count = 0
        # Process each tool
        for tool in data.get('tools', []):
            tool_count += 1
            # Check if tool exists
            cursor.execute('SELECT tool_name FROM tools WHERE tool_name = ?', (tool['tool_name'],))
            exists = cursor.fetchone()
            
            if exists:
                # Update existing tool
                cursor.execute('''
                UPDATE tools SET 
                    version = ?, 
                    primary_category = ?, 
                    short_description = ?, 
                    long_description = ?, 
                    upstream_url = ?,
                    help_command = ?, 
                    last_updated = ?
                WHERE tool_name = ?
                ''', (
                    tool.get('version', ''),
                    tool.get('primary_category', ''),
                    tool.get('short_description', ''),
                    tool.get('long_description', ''),
                    tool.get('upstream_url', ''),
                    tool.get('help_command', ''),
                    tool.get('last_updated', int(time.time())),
                    tool['tool_name']
                ))
            else:
                # Insert new tool
                cursor.execute('''
                INSERT INTO tools (
                    tool_name, version, primary_category, short_description, 
                    long_description, upstream_url, help_command, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    tool['tool_name'],
                    tool.get('version', ''),
                    tool.get('primary_category', ''),
                    tool.get('short_description', ''),
                    tool.get('long_description', ''),
                    tool.get('upstream_url', ''),
                    tool.get('help_command', ''),
                    tool.get('last_updated', int(time.time()))
                ))
            
            # Clear existing dependencies and categories
            cursor.execute('DELETE FROM dependencies WHERE tool_name = ?', (tool['tool_name'],))
            cursor.execute('DELETE FROM tool_categories WHERE tool_name = ?', (tool['tool_name'],))
            
            # Insert dependencies
            for dep in tool.get('dependencies', []):
                cursor.execute('''
                INSERT INTO dependencies (tool_name, dependency_name, is_optional)
                VALUES (?, ?, ?)
                ''', (tool['tool_name'], dep['name'], 1 if dep.get('optional') else 0))
            
            # Insert categories
            for category in tool.get('categories', []):
                cursor.execute('''
                INSERT INTO tool_categories (tool_name, category_name)
                VALUES (?, ?)
                ''', (tool['tool_name'], category))
        
        # Commit the transaction
        conn.commit()
        console.print(f"[green]Successfully imported {tool_count} tools[/green]")
        return True
    except Exception as e:
        # Rollback on error
        conn.rollback()
        console.print(f"[bold red]Error importing data:[/bold red] {e}")
        return False
    finally:
        conn.close()

def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="BlackArch Panel - Browse and search BlackArch tools")
    parser.add_argument('-c', '--category', help='List tools in a specific category')
    parser.add_argument('-s', '--search', help='Search for tools by name or description')
    parser.add_argument('-t', '--tool', help='Show details for a specific tool')
    parser.add_argument('-a', '--all', action='store_true', help='List all tools')
    parser.add_argument('-e', '--export', help='Export tools to a JSON file')
    parser.add_argument('--export-category', help='Export tools in a specific category to JSON')
    parser.add_argument('--export-search', help='Export tools matching a search term to JSON')
    
    args = parser.parse_args()
    
    check_database()
    
    if args.category:
        list_tools_in_category(args.category)
    elif args.search:
        search_tools(args.search)
    elif args.tool:
        tool_data = show_tool_details(args.tool)
        if tool_data:
            help_choice = Prompt.ask(
                "Press 'h' to view help/parameters, any other key to exit",
                default=""
            )
            if help_choice.lower() == 'h':
                execute_help_command(tool_data['help_command'])
    elif args.all:
        list_all_tools()
    elif args.export:
        export_tools_to_json(args.export)
    elif args.export_category:
        export_file = args.export or "blackarch_category_export.json"
        export_tools_to_json(export_file, 'category', args.export_category)
    elif args.export_search:
        export_file = args.export or "blackarch_search_export.json"
        export_tools_to_json(export_file, 'search', args.export_search)
    else:
        interactive_mode()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Program terminated by user.[/yellow]")
        sys.exit(0)