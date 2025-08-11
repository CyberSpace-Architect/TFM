import os
import sys

# Establish path to user-config
config_dir = os.path.join(os.path.dirname(sys.executable), "config")
os.environ["PYWIKIBOT_DIR"] = config_dir

from app.app_controller import AppController
from app.utils.db_utils import sqlite_connection, init_db

def main():
    with sqlite_connection("conflict_watcher.db") as conn:
        init_db(conn)

        wiki_crawler = AppController(conn)
        wiki_crawler.main_menu()

if __name__ == "__main__":
    main()