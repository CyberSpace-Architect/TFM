# Conflict Watcher

Master thesis project focused on developing an open-source tool, 
referred to as Conflict Watcher, focused on detecting, monitoring
and analysing edit wars within Wikipedia articles, with
the aim of extracting information that can be correlated with 
real-world geopolitical conflicts. Said tool implements the 
mutual reverts-based detection method presented by Sumi et al. in 
[Edit wars in Wikipedia](https://ieeexplore.ieee.org/document/6113205) 
to detect the presence of edit wars.

## Features

- Search of Wikipedia articles by keywords and related articles 
- Edit wars detection through the mutual reverts-based method presented by Sumi et al.
- Temporal representation of edit wars evolution
- Extraction of conflict-related information (severity, size, top mutual reverts, top reverted revisions...)
- In-depth analysis of users and revisions of selected articles
- SQLite storage and sharing of results
- Fine-grained data analysis through SQLite queries
- Automatic (and configurable) monitoring of edit wars within articles, generating a system alert when detected 
- Support for Windows and, theoretically, Unix, although the latter has not been tested 
- Compatible with articles from any language supported by Wikipedia
- Real-time adaptability to most screen resolutions


## Requirements

- Python 3.13+ (including SQLite)
- Packages listed in `requirements.txt`

## Provided build execution

1. Clone this repository:
   ```bash
   git clone https://github.com/CyberSpace-Architect/TFM.git

2. Open build/exe.*** directory (*** must be changed for the name of the directory within)
   ```bash
   cd build/exe.*** 
   
3. Execute Conflict Watcher.exe (or double-click it):
    ```bash
    ."Conflict Watcher.exe"

## For developers >>> Build own version after changes 

1. Activate provided Python virtual environment. From base project directory:
   ```bash
   .venv\scripts\activate

2. From the same directory, execute your own version of the program with:
    ```bash
    python -m app.main
   
3. To create your own build, execute (with Python virtual environment activated):
    ```bash
    python setup.py build