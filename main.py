import os
import sys
# Establish path to user-config
config_dir = os.path.join(os.path.dirname(sys.executable), "config")
os.environ["PYWIKIBOT_DIR"] = config_dir

from app_controller import AppController

def main():
    wiki_crawler = AppController()
    wiki_crawler.exec()

if __name__ == "__main__":
    main()