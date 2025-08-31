import os
import sys
from datetime import datetime

from sortedcontainers import SortedSet

# Establish path to user-config
config_dir = os.path.join(os.path.dirname(sys.executable), "config")
os.environ["PYWIKIBOT_DIR"] = config_dir

from app.utils.helpers import generate_system_notification
from app.app_controller import AppController, EditWarDetector
from app.utils.common import Singleton
from app.utils.db_utils import sqlite_connection, init_db, save_session_data


class Main(object):

    @staticmethod
    def main():
        with sqlite_connection("conflict_watcher.db") as conn:
            init_db(conn)
            app = AppController(conn)

            # Check if main is called from task scheduler instead of user
            if len(sys.argv) > 1 and sys.argv[1] == "--monitor" and sys.argv[2] == "--session_id":
                # Get args
                session_id = sys.argv[3]

                # Load data of monitored session
                app._load_session_data(session_id)

                # Check the session has articles to monitor
                singleton = Singleton()
                if singleton.articles_with_edit_war_info_dict:
                    # Get monitoring parameters
                    articles_set = SortedSet(singleton.articles_with_edit_war_info_dict.keys())
                    start_date = singleton.articles_with_edit_war_info_dict[articles_set[0]].start_date
                    update_date = datetime.now()

                    EditWarDetector.detect_edit_wars_in_monitored_articles(articles_set, start_date, update_date, session_id)

                    save_session_data(conn, session_id)

            # User execution of the program
            else:
                app.main_menu()

if __name__ == "__main__":
    Main.main()