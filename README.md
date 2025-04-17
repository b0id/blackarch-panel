# BlackArch Panel

A comprehensive tool management system for BlackArch Linux that categories metadata provides an interactive CLI for browsing, searching, and accessing information about the BlackArch tool collection.

## Features

- Browse tools by category
- Search tools by name or description
- View detailed tool information including dependencies
- Generate wrapper scripts for tools
- Find related tools with similar functionality
- Export/import tool database to JSON
- Discover new tools with the random tool feature

## Installation

### Prerequisites

- BlackArch Linux or Arch Linux with BlackArch repository configured
- Python 3.6+ with pip
- Required packages: `python-requests`, `python-beautifulsoup4`, `python-rich`

```bash
sudo pacman -S python python-pip python-requests python-beautifulsoup4 python-rich
Setup

Clone the repository:

bashgit clone https://github.com/yourusername/blackarch-panel.git
cd blackarch-panel

Generate the tool database:

bash./generate_db.py

Run the panel:

bash./bapanel.py
Usage
Interactive Mode
Simply run ./bapanel.py to enter interactive mode, where you can:

Browse tool categories
Search for specific tools
View detailed information about each tool
Access help for tools
Generate script wrappers

Command Line Arguments
The panel also supports command-line arguments:
bash# List tools in a specific category
./bapanel.py -c blackarch-scanner

# Search for tools
./bapanel.py -s "password"

# Show details for a specific tool
./bapanel.py -t nmap

# List all tools
./bapanel.py -a
License
This project is licensed under the MIT License - see the LICENSE file for details.
Acknowledgments

BlackArch Linux team for maintaining the extensive tool repository
All the developers of the individual tools

