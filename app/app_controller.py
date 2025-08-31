import heapq
import os
import pprint
import re
import logging
import sys
from pathlib import Path

import pywikibot

logging.getLogger("pywikibot.api").setLevel(logging.ERROR)

from ipwhois import IPWhois
from datetime import datetime, timedelta
from sortedcontainers import SortedSet
from babel import Locale, localedata
from sqlite3 import Connection

from app.wiki_crawler import WikiCrawler
from app.edit_war_detector import EditWarDetector
from app.info_containers.article_edit_war_info import ArticleEditWarInfo
from app.utils.helpers import Singleton, create_scheduled_task, delete_scheduled_task
from app.info_containers.local_page import LocalPage
from app.info_containers.local_revision import LocalRevision
from app.info_containers.local_user import LocalUser
from app.utils.helpers import (validate_idx, ask_valid_date, print_delim_line, clear_terminal, clear_n_lines,
                           validate_idx_in_list, datetime_to_iso, ask_yes_or_no_question, plot_graph)
from app.utils.db_utils import (reset_db, fetch_items_from_db, print_db_table, delete_from_db_table,
                                save_session_data, save_article_data, save_period_data, save_edit_war_value,
                                save_user_data, save_revision_data, save_revert_data, save_reverted_user_pair_data,
                                save_mutual_revert_data, save_mutual_reverters_activity, sanitize_and_execute_select,
                                print_query_contents, sqlite_connection, create_temp_session_db,
                                delete_non_referenced_users, update_db_table)


class AppController(object):
    __CHOOSE_OPTION_MSG = "Select an option "
    __INVALID_OPTION_MSG = "Invalid option, please select one of the list. (Enter to continue) "
    __EMPTY_SET_MSG = "Search set empty, please first search some articles with option 1. (Enter to continue) "
    __EMPTY_SESSIONS_MSG = "No sessions found in database, please save one first. (Enter to continue)"
    __CONTINUE_MSG = "\nPress Enter to continue... "
    __SIMPLE_DATE_FORMAT = "%d/%m/%Y"
    __ISO_DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


    def __init__(self, conn: Connection):
        self.articles_set = SortedSet[LocalPage]()
        self.search_categories_set = SortedSet[LocalPage]()
        self.search_articles_set = SortedSet[LocalPage]()
        self.db_conn = conn
        self.unsaved_changes = False


    def main_menu(self):
        opt = ""

        while opt != '0':
            clear_terminal()
            print_delim_line("#")
            print("[1] Search articles by keywords")
            print("[2] Search articles related to one of the articles within the set")
            print("[3] Remove article from the set")
            print("[4] Analyse presence of edit wars in articles within the set")
            print("[5] Configure automatic analysis of edit wars in articles within the set")
            print("[6] Stop automatic analysis of edit wars previously configured")
            print("[7] Analyse an article of the set in-depth")
            print("[8] Manage stored sessions")
            print("[0] Exit\n")

            opt = input(self.__CHOOSE_OPTION_MSG)
            match opt:
                case '1':
                    # Ask user about search parameters
                    search, limit, _ = self.__obtain_search_parameters()

                    # Crawl wikipedia for articles
                    pages = WikiCrawler.crawl_articles(search, search_limit=limit, search_type=0)

                    # Save results in SortedSet as PageGenerator only allows to iterate it once
                    for page in pages:
                        self.search_articles_set.add(LocalPage.init_with_page(page))

                    # Inform user and return to main menu if search yielded no results
                    if len(self.search_articles_set) == 0:
                        input("Search yielded no results (Enter to continue) ")
                        continue

                    # New menu until user wants to return
                    self.__searched_articles_menu()

                case '2':
                    # Check articles set has at least 1 article to search related categories
                    if len(self.articles_set) == 0:
                        input(self.__EMPTY_SET_MSG)
                        continue    # Return to main menu

                    # Show search set
                    WikiCrawler.print_pages(self.articles_set)
                    print(f'\nArticles in search set: {len(self.articles_set)}\n')

                    idx = input("Select nº of the article for which you want to search related categories (0 to return) ")
                    idx = int(validate_idx(idx, 0, len(self.articles_set)))

                    if idx == 0:
                        continue    # Return to main menu

                    # Extract related categories
                    pages = self.articles_set[idx-1].categories()

                    # Save results in SortedSet as PageGenerator only allows to iterate it once
                    for page in pages:
                        self.search_categories_set.add(LocalPage.init_with_page(page))

                    if len(self.search_categories_set) == 0:
                        clear_terminal()
                        input("No related categories for this article (Enter to continue) ")
                        continue     # Return to main menu

                    # New menu until user wants to return
                    opt_2 = ""
                    while opt_2 != '0':
                        opt_2 = self.__searched_categories_menu()
                    self.search_categories_set.clear()  # Clear search categories set once user finishes using it

                case '3':
                    # Check articles set has at least 1 article to delete
                    if len(self.articles_set) == 0:
                        input(self.__EMPTY_SET_MSG)
                        continue

                    # New menu until user wants to return
                    opt_2 = ""
                    while opt_2 != '0':
                        opt_2 = self.__delete_articles_menu()

                case '4':
                    # Check articles set is not empty before calculating edit-war values
                    if len(self.articles_set) == 0:
                        input(self.__EMPTY_SET_MSG)
                        continue     # Return to main menu

                    # Ask and validate a start date
                    msg = ("Specify start date (dd/mm/YYYY) to count revisions of searched articles (leave blank and "
                           "press Enter to use past 30 days) ")
                    default_value = datetime.now() - timedelta(days=30)
                    start_date = ask_valid_date(msg, default_value, self.__SIMPLE_DATE_FORMAT)

                    # Ask and validate an end date
                    msg = ("Specify end date (dd/mm/YYYY) to count revisions of searched articles"
                           " (leave blank and press Enter to use current date) ")
                    default_value = datetime.now()
                    end_date = ask_valid_date(msg, default_value, self.__SIMPLE_DATE_FORMAT)

                    # Swap dates if they are mixed
                    if start_date > end_date:
                        start_date, end_date = end_date, start_date

                    # Detect edit wars in all articles of the set
                    EditWarDetector.detect_edit_wars_in_set(self.articles_set, start_date, end_date)

                    # Show results
                    print_delim_line("-")
                    print("Summary of results:\n")
                    EditWarDetector.print_pages_with_tags(Singleton().articles_with_edit_war_info_dict)
                    input(self.__CONTINUE_MSG)

                case '5':
                    # Check articles set has at least 1 article to monitor
                    if len(self.articles_set) == 0:
                        input(self.__EMPTY_SET_MSG)
                        continue

                    self.__start_monitoring_menu()

                case '6':
                    # New menu until user wants to return
                    opt_2 = ""
                    while opt_2 != '0':
                        opt_2 = self.__stop_monitoring_sessions_menu()

                case '7':
                    # Check articles set has at least 1 article to inspect
                    if len(self.articles_set) == 0:
                        input(self.__EMPTY_SET_MSG)
                        continue  # Return to main menu

                    # Check edit wars detection has been made before inspection
                    if len(Singleton().articles_with_edit_war_info_dict) == 0:
                        input('Please, select option 3 in main menu before requesting in-depth analysis '
                              'of an article (Enter to continue) ')
                        continue  # Return to main menu

                    # New menu until user wants to return
                    opt_2 = ""
                    while opt_2 != '0':
                        opt_2 = self.__select_article_to_inspect_menu()

                case '8':
                    # New menu until user wants to return
                    opt_2 = ""
                    while opt_2 != '0':
                        opt_2 = self.__manage_sessions_menu()

                case '0':
                    # Check changes not saved and ask user to save them before leaving the program
                    if self.unsaved_changes:
                        question = "Data not saved, do you want to save it before exit? "
                        answer = ask_yes_or_no_question(question)

                        if answer:
                            self.__save_session_menu()

                        clear_terminal()
                case _:
                    input(self.__INVALID_OPTION_MSG)


    @staticmethod
    def __obtain_search_parameters() -> [str, int, str]:
        # Ask keywords for search
        search = input("What do you want to search for? ")

        while search == "":
            search = input("Search field cannot be empty, please try again ")

        # Max nº of articles to search
        limit = input("How many pages do you want to search at most? (Enter for no limit) ")

        # Check limit is an empty string representing no limit or a positive number
        while limit != "" and (not limit.isdigit() or int(limit) <= 0):
            limit = input("Invalid limit, introduce a value higher than zero ")

        limit = None if limit == "" else int(limit)     # Adapt limit to the format that pywikibot requires

        # Select search language (last search language by default, english if no previous searches)
        language = Locale(WikiCrawler.language_code).get_display_name('en') # type: ignore
                                                                            # --> 'en' param. is necessary to get
                                                                            # language in english (false positive)
        question = f'Language selected for search: {language}, do you want to change it? '
        answer = ask_yes_or_no_question(question)

        if answer:
            # Get names in english of all the available languages and print them
            language_codes = sorted(pywikibot.family.Family.load("wikipedia").langs.keys())
            idx = 0
            language_list = []

            while idx < len(language_codes):
                code = language_codes[idx]
                if localedata.exists(code):
                    language = Locale(code).get_display_name('en') # type: ignore
                                                                   # --> 'en' param. is necessary to get
                                                                   # language in english (false positive)
                    print(f'[{idx+1}] {language}')
                    language_list.append(language)
                    idx += 1
                else:
                    language_codes.pop(idx)

            # Ask user about the language desired for the search
            idx = int(validate_idx(input("\nFrom the list above, select the number of the Wiki language you want to "
                                         "search in "), 1, len(language_codes)))

            # Set the language selected
            WikiCrawler.set_language_code(language_codes[idx-1])
            language = Locale(language_codes[idx-1]).get_display_name('en') # type: ignore
                                                                            # --> 'en' param. is necessary to get
                                                                            # language in english (false positive)

        return search, limit, language


    def __searched_articles_menu(self) -> str:
        clear_terminal()
        print_delim_line("#")

        # Show search results
        WikiCrawler.print_pages(self.search_articles_set)
        print(f'\nResults found: {len(self.search_articles_set)}')
        print_delim_line("-")

        # Keep showing options until user has added all desired articles
        idx = ""
        shared_dict = Singleton().shared_dict

        while idx != '0':
            # Show articles added to set
            if len(self.articles_set) == 0:
                print("No articles added yet\n")
                shared_dict["lines_to_remove"] = shared_dict.get("lines_to_remove", 0) + 2
            else:
                WikiCrawler.print_pages(self.articles_set, will_remove_lines=True)
                print("\nArticles added: " + str(len(self.articles_set)) + "\n")
                shared_dict["lines_to_remove"] = shared_dict.get("lines_to_remove", 0) + 4

            # Show options
            idx = validate_idx(input("Select nº of the article you want to add to search set (0 to return) "),
                                     0, len(self.search_articles_set))
            shared_dict["lines_to_remove"] = shared_dict.get("lines_to_remove", 0) + 1

            if idx != '0':
                # Add article to the set that the application works with
                local_page = self.search_articles_set[int(idx)-1]
                self.articles_set.add(local_page)

                # Indicate that new data should be saved in database
                self.unsaved_changes = True

                clear_n_lines(shared_dict.get("lines_to_remove", 0))
            else:
                self.search_articles_set.clear()

            shared_dict["lines_to_remove"] = 0

        return idx


    def __searched_categories_menu(self) -> str:
        # Show search results
        clear_terminal()
        print_delim_line("#")
        WikiCrawler.print_pages(self.search_categories_set)
        print(f'\nResults found: {len(self.search_categories_set)}\n')

        # Ask user for the category to search
        idx = validate_idx(input("Select nº of the category in which you want to search articles (0 to return) "),
                       0, len(self.search_categories_set))

        if idx != '0':
            limit = input("How many pages do you want to search at most? (Enter for no limit) ")

            # Check limit is an empty string representing no limit or a positive number
            while limit != "" and (not limit.isdigit() or int(limit) <= 0):
                limit = input("Invalid limit, introduce a value higher than zero ")

            limit = None if limit == "" else int(limit)     # Adapt limit to the format that pywikibot requires

            # Search articles within selected category
            pages = WikiCrawler.crawl_articles((self.search_categories_set[int(idx)-1]).title, search_limit=limit, search_type=1)

            # Store results
            for page in pages:
                self.search_articles_set.add(LocalPage.init_with_page(page))

            if len(self.search_articles_set) == 0:
                input("Search yielded no results try another category (Enter to continue) ")
            else:
                self.__searched_articles_menu()     # Show menu with searched articles

        return idx


    def __delete_articles_menu(self) -> str:
        # Show articles in set
        clear_terminal()
        print_delim_line("#")
        WikiCrawler.print_pages(self.articles_set)
        print(f'\nArticles in search set: {len(self.articles_set)}\n')

        # Show options
        idx = validate_idx(input("Select " + "nº of the article you want to delete from search set (0 to return) "),
                        0, len(self.articles_set))
        if idx != '0':
            # Get article and delete it from set
            article = self.articles_set[int(idx) - 1]
            self.articles_set.pop(int(idx)-1)

            # If edit war info has already been stored about this article it is deleted
            info_dict = Singleton().articles_with_edit_war_info_dict
            if len(info_dict) != 0 and info_dict.get(article):
                info_dict.pop(article)

            # Indicate that new data should be saved in database
            self.unsaved_changes = True

        return idx


    def __start_monitoring_menu(self):
        # Ask user about the analysis frequency
        frequency = input("Every how many days do you want the session to be analysed? ")

        valid_frequency = False
        while not valid_frequency:
            frequency = re.sub(r"\s+", "", frequency)
            if not frequency.isdigit() or int(frequency) < 1:
                frequency = input("Invalid frequency, please, indicate a valid number of days to perform the "
                                  "analysis ")
            else:
                valid_frequency = True

        articles_with_edit_war_info_dict: dict = Singleton().articles_with_edit_war_info_dict

        # Articles have not been previously analysed, so new periods are created for each article starting from today
        if not articles_with_edit_war_info_dict:
            start_date = datetime.now().replace(microsecond=0)
            end_date = datetime.now().replace(microsecond=0)

            for local_page in self.articles_set:
                articles_with_edit_war_info_dict[local_page] = ArticleEditWarInfo(local_page, start_date, end_date)

        # Articles have been previously analysed, so it must be checked that the analysis period goes until today, if
        # not it must be adjusted to start the monitoring, otherwise it is canceled
        else:
            # Get end date from first article
            info = list(articles_with_edit_war_info_dict.values())[0]
            end_date = info.end_date

            # If analysis period is incompatible, the user is asked, otherwise monitoring is configured right away
            if end_date < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
                answer = ask_yes_or_no_question("Articles have been previously analysed but the time period "
                                                "does not finish in current date, which is necessary to start "
                                                "monitoring, do you want to complete the analysis until today? ")

                if answer in {"y", "yes"}:
                    EditWarDetector.detect_edit_wars_in_set(SortedSet(articles_with_edit_war_info_dict.keys),
                                                            info.start_date, datetime.now().replace(microsecond=0))
                else:
                    answer = ask_yes_or_no_question("Do you want instead to delete previous data and start a clean "
                                                    "monitoring from today? ")

                    if answer in {"y", "yes"}:
                        # New periods are created for each article starting from today
                        for local_page in articles_with_edit_war_info_dict.keys():
                            start_date = datetime.now().replace(microsecond=0)
                            end_date = datetime.now().replace(microsecond=0)

                            articles_with_edit_war_info_dict[local_page] = (
                                ArticleEditWarInfo(local_page, start_date, end_date))

                        Singleton().users_info_dict.clear()

        # Save data to allow the scheduled task to retrieve data from database when app is not being executed
        input("Current session will now be saved to allow articles to be monitored, press Enter to continue...")

        # Show sessions stored
        clear_terminal()
        print_delim_line("#")
        sessions = print_db_table(self.db_conn, "sessions")

        if not sessions:
            print("No sessions found in database")

        # Save current session
        session_id = self.__save_session_menu()
        self.unsaved_changes = False  # Changes saved so flag is deactivated

        # Get parameters for the task
        task_name = f'conflict_watcher_session_{session_id}_monitor'
        directory_path = os.path.dirname(os.path.abspath(__file__))
        #directory_path = os.path.dirname(os.path.abspath(__file__))     # Change for development only (app directory)

        execution_path = directory_path
        #execution_path = os.path.dirname(directory_path)                # Change for development only (Conflict Watcher directory)
        #input(str(execution_path))

        script_path = os.path.dirname(directory_path)
        script_path = Path(os.path.dirname(script_path))
        script_path = script_path / "Conflict Watcher.exe"
        #script_path = os.path.join(directory_path, "main.py")           # Change for development only
        args = f'--monitor --session_id {session_id}'

        # Create task
        create_scheduled_task(task_name, int(frequency), execution_path, script_path, args)

        # Mark session as monitored
        update_db_table(self.db_conn, "sessions", "monitored=?", [True], str(session_id))


    def __stop_monitoring_sessions_menu(self):
        # Show monitored sessions in database
        clear_terminal()
        print_delim_line("#")

        # Sanitize_and_execute_select function is used instead of fetch_items_from_db because the latter does not
        # return the cursor description (column names) needed to print the results with print_query_contents
        results = sanitize_and_execute_select(self.db_conn, "SELECT * FROM sessions WHERE monitored=1")
        description, rows = results
        print_query_contents(description, rows)

        # 0 is added right-away to allow return option
        monitored_sessions_ids_list = [0]
        for session in rows:
            monitored_sessions_ids_list.append(session[0])

        print(f'\nSessions being monitored: {len(rows)}\n')
        print_delim_line("-")

        # Ask user about the session that wants to stop monitoring
        session_id = validate_idx_in_list(input("Select " + "ID of the session you want to stop monitoring: "
                                                            "(0 to return) "), monitored_sessions_ids_list)

        if session_id != '0':
            # Stop monitoring task for this session
            delete_scheduled_task(session_id)

            # Change monitored value of session in database
            update_db_table(self.db_conn, "sessions", "monitored=?",
                            [False], session_id)

            # Update stored_sessions_ids_list
            monitored_sessions_ids_list.remove(int(session_id))

        clear_n_lines(5 + len(rows) + 4 + Singleton().shared_dict["lines_to_remove"])

        return session_id


    def __select_article_to_inspect_menu(self) -> str:
        # Show articles with edit war tags from Singleton dict
        clear_terminal()
        print_delim_line("#")
        info_dict = Singleton().articles_with_edit_war_info_dict
        ids_dict = EditWarDetector.print_pages_with_tags(info_dict)  # Retrieve ids to access info later
        print(f'\nArticles in search set: {len(self.articles_set)}\n')

        article_id = validate_idx(input("Select nº of the article you want to inspect (0 to return) "),
                                  0, len(self.articles_set))
        if article_id != '0':
            local_page = ids_dict[int(article_id)]  # Selected article to inspect

            # New menu until user wants to return
            opt = ""
            while opt != '0':
                opt = self.__inspect_article_in_depth_menu(local_page)

        return article_id


    def __inspect_article_in_depth_menu(self, local_page: LocalPage) -> str:
        # Show article info as it is calculated
        clear_terminal()
        print_delim_line("#")
        print(f'Selected article: {local_page.title} ({local_page.full_url()})')

        print_delim_line("-")
        print("Article info:")
        info = Singleton().articles_with_edit_war_info_dict[local_page]

        # Conflict severity (edit war value for the whole time period)
        edit_war_value = info.edit_war_over_time_list[-1][0]
        print(f'\n\t- Conflict severity (edit war value, higher than '
              f'{EditWarDetector.EDIT_WAR_THRESHOLD} is considered edit war): {edit_war_value}')

        # Conflict's size (nº of users mutually reverting each other)
        if not info.mutual_reverters_dict:
            for mutual_reverts_tuple in info.mutual_reverts_list:
                user_i = mutual_reverts_tuple[0][1].user
                user_j = mutual_reverts_tuple[1][1].user
                info.mutual_reverters_dict[user_i] = info.mutual_reverters_dict.get(user_i, 0) + 1
                info.mutual_reverters_dict[user_j] = info.mutual_reverters_dict.get(user_j, 0) + 1

        n_mutual_reverters = len(info.mutual_reverters_dict)
        print(f'\n\t- Conflict\'s size (nº of users mutually reverting each other): {n_mutual_reverters}')

        # Conflict's temporal evolution
        self._print_conflict_evolution(info)

        # Fighting editors ordered from higher to lower activity (based on the nº of mutual reverts made)
        ordered_mutual_reverters_dict = dict(sorted(info.mutual_reverters_dict.items(), key=lambda item: item[1],
                                                    reverse=True))

        print("\n\t- Fighting editors ordered from higher to lower conflicting activity (nº of mutual reverts made): ")
        print("\n\t\tRANK --> EDITOR --> Nº OF MUTUAL REVERTS")
        for i, (user_i, edits) in enumerate(ordered_mutual_reverters_dict.items()):
            print(f'\t\t{i + 1} --> {user_i} --> {edits}')

        # Top 10 most reverted revisions, along with the number of reverts
        reverted_revisions_dict = self._print_most_reverted_revisions(info)

        # Show options
        print_delim_line("-")
        print("[1] Inspect article's history page")
        print("[2] Inspect article's discussion page")
        print("[3] Inspect a user from the list")
        print("[4] Inspect a revision from the list")
        print("[0] Return to articles' list\n")

        opt = input(self.__CHOOSE_OPTION_MSG)
        match opt:
            case '1':
                # Show history page
                clear_terminal()
                print_delim_line("#")
                self.unsaved_changes = WikiCrawler.print_pages(SortedSet({local_page}),
                                                               time_range=(info.start_date, info.end_date),
                                                               history_changes=True)
                input(self.__CONTINUE_MSG)
            case '2':
                # Show discussion page
                clear_terminal()
                print_delim_line("#")
                self.unsaved_changes = WikiCrawler.print_pages(SortedSet({local_page}),
                                                               time_range=(info.start_date, info.end_date),
                                                               discussion_changes=True)
                input(self.__CONTINUE_MSG)
            case '3':
                # Show user info, new menu until user wants to return
                self.__inspect_user_menu(info)
            case '4':
                # Show revision info, new menu until user wants to return
                self.__inspect_revision_menu(info, reverted_revisions_dict)
            case '0':
                pass  # Return
            case _:
                input(self.__INVALID_OPTION_MSG)  # No value needed from input, used to inform user

        return opt


    def _print_conflict_evolution(self, info: ArticleEditWarInfo):
        print("\n\t- Conflict's temporal evolution (graph with edit war values over time): ")
        intervals = ArticleEditWarInfo.split_time_interval(info.start_date, info.end_date)
        x_vals, y_vals = [], []

        # If values are already stored, they are directly assigned to graph's values
        if len(info.edit_war_over_time_list) > 1:
            for i, interval_end_date in enumerate(intervals):
                x_vals.append(interval_end_date.strftime(self.__SIMPLE_DATE_FORMAT))
                y_vals.append(int(info.edit_war_over_time_list[i][0]))

        else:  # Otherwise, they are calculated
            print("\n\t==> Calculating edit war values to plot...\n")

            # Calculate edit war values for each of the intervals. To do so, the revs_list of each interval has to
            # be created incrementally, except for the final interval (complete time range) previously calculated
            revs_list = []
            last_rev_idx = 0

            # Save last value (complete time range) as it is already calculated in graph's values
            x_vals.append(intervals[-1].strftime(self.__SIMPLE_DATE_FORMAT))
            y_vals.append(int(info.edit_war_over_time_list[-1][0]))

            # Indicate that new data should be saved in database
            self.unsaved_changes = True

            for i, interval_end_date in enumerate(intervals[:-1]):

                # For each interval create the list of revisions published within it
                for local_rev in info.revs_list[last_rev_idx:]:
                    rev_date = datetime.strptime(local_rev.timestamp, self.__ISO_DATE_FORMAT)

                    if rev_date > interval_end_date:
                        break

                    revs_list.append(local_rev)
                    last_rev_idx += 1

                # Calculate the edit war value of the revisions within the interval
                _, _, edit_war_value = EditWarDetector.is_article_in_edit_war(revs_list)
                info.edit_war_over_time_list.insert(-1, (edit_war_value, interval_end_date))

                # Save interval results in graph's values (penultimate position as last value is already stored)
                x_vals.insert(-1, interval_end_date.strftime(self.__SIMPLE_DATE_FORMAT))
                y_vals.insert(-1, int(edit_war_value))

                clear_n_lines(1)
                print(f'\t\tIntervals with edit war value calculated {i + 2}/{len(intervals)}')

            clear_n_lines(3)

        print("\n")

        plot_graph(title="CONFLICT'S TEMPORAL EVOLUTION", x_label="TIME", y_label="EDIT WAR VALUES",
                   x_vals=x_vals, y_vals=y_vals)


    @staticmethod
    def _print_most_reverted_revisions(info: ArticleEditWarInfo) -> dict:
        # Create a dictionary where, for each revision, a set with all the revisions that revert to it is stored
        reverted_revisions_dict = {}
        for reverted_rev, revertant_rev, reverted_users in info.reverts_list:
            if reverted_rev.revid not in reverted_revisions_dict:
                reverted_revisions_dict[reverted_rev.revid] = [reverted_rev, [revertant_rev]]
            else:
                reverted_revisions_dict[reverted_rev.revid][1].append(revertant_rev)

        # Extract top 10 most reverted revisions
        top10 = heapq.nlargest(10, reverted_revisions_dict.items(), key=lambda item: len(item[1][1]))

        print(f'\n\t- Top {len(top10)} most reverted revisions, along with the number of reverts (a high number may '
              f'indicate bots\' presence, trying to impose the narrative of a particular revision): ')
        print("\n\t\tRANK --> [REVISION ID, TIMESTAMP, AUTHOR] --> Nº OF REVERTS TO THAT REVISION")
        for i, (rev_id, [rev, reverts_list]) in enumerate(top10):
            print(f'\t\t{i + 1} --> [{rev_id}, {rev.timestamp}, {rev.user}] '
                  f'--> {len(reverts_list)}')

        return reverted_revisions_dict


    def __inspect_user_menu(self, info: ArticleEditWarInfo):
        # Ask user for the name of the mutual reverter that wants to inspect
        username = input("Please indicate the name of the user you want to inspect ")

        while not info.mutual_reverters_dict.get(username):
            username = input("Name not found on the list, please try again ")

        # Retrieve info about the user
        users_info_dict = Singleton().users_info_dict
        user_info = users_info_dict.get(username)

        # If any required info about the user is missing, it is retrieved from Wikipedia
        if not user_info or user_info.is_registered is None or (
                user_info.is_registered == False and user_info.asn is None):
            # Create a User object from Wikipedia to retrieve info and create a user_info object
            user = pywikibot.User(WikiCrawler.site, username)

            username = user.username
            is_registered = user.isRegistered()
            is_blocked = user.is_blocked()
            registration = user.registration()
            edit_count = user.editCount()

            user_info = LocalUser(username, str(WikiCrawler.site), is_registered, is_blocked, registration, edit_count)

            # Print user info
            clear_terminal()
            print_delim_line("#")
            print(f'Selected user: {username}')
            print_delim_line("-")
            print("User info:")
            print(f'\n\t- Username: {username} \n\n\t- Is registered?: {is_registered} '
                  f'\n\n\t- Is blocked?: {is_blocked} \n\n\t- Registration date: {registration} '
                  f'\n\n\t- Nº of global user edits (0 for anonymous users, ie. IP) {edit_count}')

            # Check if the username corresponds to an IP address (editor not registered in Wikipedia), if it is the case
            # a Whois request is made and additional info printed
            ipv4_pattern = r'^((25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.|$)){4}$'
            ipv6_pattern = r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'
            if re.fullmatch(ipv4_pattern, username) or re.fullmatch(ipv6_pattern, username):
                # Make Whois request and store and print info as it is extracted from the results
                whois = IPWhois(user.username)
                result = whois.lookup_rdap()

                network = result.get("network", {})
                user_info.asn = result["asn"]
                user_info.asn_description = result["asn_description"]
                not_available_msg = "Info not available"
                user_info.network_address = network.get("handle", not_available_msg)
                user_info.network_name = network.get("name", not_available_msg)
                user_info.network_country = network.get("country", not_available_msg)

                print(f'\n\t- ASN: {user_info.asn} ({user_info.asn_description})')
                print(f'\n\t- Network: {user_info.network_address} ({user_info.network_name}) '
                      f'\n\n\t- Country: {user_info.network_country}')

                # Registrants info must be parsed before storing and printing
                objects = result.get("objects", {})
                registrants_dict: dict[str, dict] = {}
                for object_name, object_info in objects.items():
                    if object_info.get("roles", []) == ["registrant"]:
                        registrants_dict[object_name] = object_info

                if len(registrants_dict) > 0:
                    print("\n\t- Registrants info: ")
                    tabbed_info = None

                    for object_name, object_info in registrants_dict.items():
                        print(f'\n\t{object_name}: ')
                        formatted_info = pprint.pformat(object_info, indent=2)
                        tabbed_info = '\n'.join('\t' + line for line in formatted_info.splitlines())
                        user_info.registrants_info = tabbed_info
                        print(tabbed_info)

                    user_info.registrants_info = tabbed_info

            users_info_dict[username] = user_info

            # Indicate that new data should be saved in database
            self.unsaved_changes = True

        # Otherwise, all required info about the user is stored, so it is simply printed
        else:
            self._print_user_info(user_info)

        input(self.__CONTINUE_MSG)


    @staticmethod
    def _print_user_info(user_info: LocalUser):
        # Print all info stored about the user
        clear_terminal()
        print_delim_line("#")
        print(f'Selected user: {user_info.username}')
        print_delim_line("-")
        print("User info:")
        print(f'\n\t- Username: {user_info.username} \n\n\t- Is registered?: {user_info.is_registered} '
              f'\n\n\t- Is blocked?: {user_info.is_blocked} \n\n\t- Registration date: {str(user_info.registration_date)} '
              f'\n\n\t- Nº of global user edits (0 for anonymous users, ie. IP) {user_info.edit_count}')

        # In case that the username corresponds to an IP address additional info is printed
        ipv4_pattern = r'^((25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.|$)){4}$'
        ipv6_pattern = r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'
        if re.fullmatch(ipv4_pattern, user_info.username) or re.fullmatch(ipv6_pattern, user_info.username):
            print(f'\n\t- ASN: {user_info.asn} ({user_info.asn_description})')
            print(f'\n\t- Network: {user_info.network_address} ({user_info.network_name}) '
                  f'\n\n\t- Country: {user_info.network_country} \n\n\t- Registrants info: {user_info.registrants_info}')


    def __inspect_revision_menu(self, info: ArticleEditWarInfo, reverted_revisions_dict: dict):
        # Ask user for the id of the revision that wants to inspect
        rev_id = input("Please indicate the ID of the revision you want to inspect ")

        # Search rev with given id and keep asking for a correct id while no matching rev is found
        selected_local_rev = None
        while selected_local_rev is None:
            for local_rev in info.revs_list:
                if str(local_rev.revid) == rev_id:
                    selected_local_rev = local_rev
                    break

            if selected_local_rev is None:
                rev_id = input("ID not found on article's history page, please try a different one ")

        # Print revision info
        clear_terminal()
        print_delim_line("#")
        print(f'Selected revision: {str(selected_local_rev.revid)}')
        print_delim_line("-")
        print("Revision info:")
        print(f'\n\t- ID: {str(selected_local_rev.revid)} \n\n\t- Timestamp: {selected_local_rev.timestamp} '
              f'\n\n\t- Author: {selected_local_rev.user} '
              f'\n\n\t- Comment: {selected_local_rev.comment}')

        print("\n\t- List of reverts made to this revision: ")
        reverts_list = reverted_revisions_dict[int(rev_id)][1]
        print("\n\t\tREV ID, TIMESTAMP, USER")
        for local_rev in reverts_list:
            print(f'\n\t\t{str(local_rev.revid)}, {local_rev.timestamp}, {local_rev.user}')

        # If the text of the revision is not stored, it is retrieved from Wikipedia
        if not selected_local_rev.text:
            rev_date = datetime.strptime(selected_local_rev.timestamp, self.__ISO_DATE_FORMAT)
            fam, code = info.article.site.split(":", 1)
            site = pywikibot.Site(code, fam)

            if not info.article.page:
                info.article.page = next(site.load_pages_from_pageids([info.article.pageid]))

            local_rev_list = WikiCrawler.get_full_revisions_in_range(site, info.article.page, rev_date, rev_date,
                                                                     include_text=True)

            contents = local_rev_list[0].revision['slots']['main'].get('*', None)
        else:
            contents = selected_local_rev.text

        # The text of a revision may not be publicly available, in which case it is informed
        if contents is None:
            print("\n\t- Contents: Not publicly available (deleted or protected)")

        else:  # Otherwise, it is stored and printed
            selected_local_rev.text = contents
            print(f'\n\t- Contents: \n\n{contents}')

            # Indicate that new data should be saved in database
            self.unsaved_changes = True

        input(self.__CONTINUE_MSG)


    def __manage_sessions_menu(self) -> str:
        # Show sessions stored
        clear_terminal()
        print_delim_line("#")
        sessions = print_db_table(self.db_conn, "sessions")

        if not sessions:
            print("No sessions found in database")

        # Store session ids to access them later (0 is also stored to allow user to indicate that wants to return)
        stored_sessions_ids_list = [0]
        for session in sessions:
            stored_sessions_ids_list.append(session[0])

        # Show options
        print_delim_line("-")
        print("[1] Load data from a previous session")
        print("[2] Save current session")
        print("[3] Delete a saved session")
        print("[4] Make a custom SQL query to the database")
        print("[5] Reset database")
        print("[0] Return to main menu \n")

        opt = input(self.__CHOOSE_OPTION_MSG)
        match opt:
            case '1':
                # Load data from a previous session
                session_id = validate_idx_in_list(input("\nSelect nº of the session you want to load (0 to return) "),
                                             stored_sessions_ids_list)
                session = None
                if session_id != '0':
                    for session in sessions:
                        if session[0] == int(session_id):
                            break

                    self._load_session_data(session_id)

            case '2':
                # Save current session
                self.__save_session_menu()
                self.unsaved_changes = False    # Changes saved so flag is deactivated

            case '3':
                # Delete a saved session
                if len(sessions) == 0:
                    input(self.__EMPTY_SESSIONS_MSG)
                else:
                    # New menu until user wants to return
                    opt_2 = ""
                    while opt_2 != '0':
                        opt_2 = self.__delete_session_menu(stored_sessions_ids_list)

            case '4':
                # Make a custom SQL query to the database
                if len(sessions) == 0:
                    input(self.__EMPTY_SESSIONS_MSG)
                else:
                    # Ask user about the session that wants to query
                    session_id = validate_idx_in_list(input("\nSelect nº of the session you want to query "
                                                            "(0 to return) "), stored_sessions_ids_list)
                    if session_id != '0':
                        # Assign a path for temporal database with a copy of the session data
                        temp_db_path = "temp_session.db"

                        # Look for the session
                        for session in sessions:
                            if session[0] == int(session_id):
                                # Ensure temporal db file do not exist before connecting to it
                                if os.path.exists(temp_db_path):
                                    os.remove(temp_db_path)

                                # Create temporal database with data from selected session
                                with sqlite_connection(temp_db_path) as create_temp_db_conn:
                                    create_temp_session_db(self.db_conn, create_temp_db_conn, session)

                                # New menu until user wants to return
                                opt_2 = ""
                                while opt_2 != '0':
                                    opt_2 = self.__query_session_menu()
                                break # Stop loop once session was already found and queried

                        # Remove temporal database file after closing the connection to it
                        if os.path.exists(temp_db_path):
                            os.remove(temp_db_path)

            case '5':
                # Reset database
                # Ask user to confirm the action to avoid miss clicks
                question = ("Resetting the database will delete all previous information stored including all previous "
                            "sessions, are you sure you want to reset the it? ")
                answer = ask_yes_or_no_question(question)

                if answer:
                    # Delete database and create a new one
                    reset_db(self.db_conn)
            case '0':
                pass # Return
            case _:
                input(self.__INVALID_OPTION_MSG)

        return opt


    def _load_session_data(self, session_id: str):
        # First of all, data currently loaded in the tool must be deleted to avoid mixing information
        singleton = Singleton()
        singleton.articles_with_edit_war_info_dict.clear()
        singleton.users_info_dict.clear()
        singleton.shared_dict.clear()

        # 1º Load data in articles_set from articles' table
        session_articles = fetch_items_from_db(self.db_conn, "articles", "session = ?", [session_id])
        articles_ids_dict:dict[str, LocalPage] = {}

        for article in session_articles:
            pageid = article[2]
            title = article[4]
            url = article[5]
            site = article[6]
            namespace = article[7]
            content_model = article[8]
            text = article[9]
            discussion_page_title = article[10]
            discussion_page_url = article[11]
            discussion_page_text = article[12]

            local_page = LocalPage(pageid, title, site, namespace, url, content_model, discussion_page_title,
                                   discussion_page_url, text=text, discussion_page_text=discussion_page_text)

            self.articles_set.add(local_page)
            articles_ids_dict[article[1]] = local_page

        # 2º Load data in _articles_with_edit_war_info_dict from edit_war_analysis_periods' table
        session_periods = fetch_items_from_db(self.db_conn, "edit_war_analysis_periods", "article IN (",
                                              list(articles_ids_dict.keys()), in_clause=True)

        articles_with_edit_war_info_dict = Singleton().articles_with_edit_war_info_dict

        periods_ids_dict: dict[str, LocalPage] = {}
        for period in session_periods:
            article = articles_ids_dict[period[2]]
            start_date = datetime.strptime(period[3], self.__ISO_DATE_FORMAT) if period[2] else None
            end_date = datetime.strptime(period[4], self.__ISO_DATE_FORMAT) if period[2] else None
            edit_war_notified = period[5] if period[2] else None

            article_info = ArticleEditWarInfo(article, start_date, end_date, edit_war_notified)

            articles_with_edit_war_info_dict[article] = article_info
            periods_ids_dict[period[1]] = article

        # 3º Load data in _articles_with_edit_war_info_dict from edit_war_values' table
        session_values = fetch_items_from_db(self.db_conn, "edit_war_values", "period IN (",
                                              list(periods_ids_dict.keys()), in_clause=True)

        for edit_war_value in session_values:
            article = periods_ids_dict[edit_war_value[1]]
            info = articles_with_edit_war_info_dict[article]
            date = datetime.strptime(edit_war_value[2], self.__ISO_DATE_FORMAT) if edit_war_value[2] else None
            value = edit_war_value[3]

            info.edit_war_over_time_list.append((value, date))


        # 4º Load data in _articles_with_edit_war_info_dict from revisions' table
        session_revisions = fetch_items_from_db(self.db_conn, "revisions", "article IN (",
                                             list(articles_ids_dict.keys()), in_clause=True)
        revisions_ids_dict: dict[str, (LocalPage, LocalRevision)] = {}
        users_ids_set = set[str]()

        for rev in session_revisions:
            article = articles_ids_dict[rev[3]]
            info = articles_with_edit_war_info_dict[article]
            revid = rev[2]
            timestamp = rev[4]
            user = rev[5]
            text = rev[6]
            size = rev[7]
            tags = rev[8]
            comment = rev[9]
            sha1 = rev[10]

            local_rev = LocalRevision(revid, timestamp, user, text, size, tags, comment, sha1)

            info.revs_list.append(local_rev)
            revisions_ids_dict[rev[1]] = (article, local_rev)
            users_ids_set.add(user)     # Keep username references as we will need them later to search users' table

        # 5º Load data in _articles_with_edit_war_info_dict from reverts' table
        session_reverts = fetch_items_from_db(self.db_conn, "reverts", "revertant_rev IN (",
                                                list(revisions_ids_dict.keys()), in_clause=True)
        reverts_ids_dict: dict[str, (LocalPage, LocalRevision)] = {}

        for session_revert in session_reverts:
            article, rev = revisions_ids_dict[session_revert[1]]
            info = articles_with_edit_war_info_dict[article]
            revertant_rev = revisions_ids_dict[session_revert[1]][1]
            reverted_rev = revisions_ids_dict[session_revert[2]][1]
            reverted_users_set = set[str]()

            revert = (revertant_rev, reverted_rev, reverted_users_set)

            info.reverts_list.append(revert)
            reverts_ids_dict[session_revert[1]] = (article, rev)

        # 6º Load data in _articles_with_edit_war_info_dict from mutual_reverts' table
        session_mutual_reverts = fetch_items_from_db(self.db_conn, "mutual_reverts", "revertant_rev_1 "
                                                     "IN (", list(reverts_ids_dict.keys()), in_clause=True)

        for mutual_revert in session_mutual_reverts:
            article, rev = reverts_ids_dict[mutual_revert[2]]
            info = articles_with_edit_war_info_dict[article]
            revertant_rev_1 = revisions_ids_dict[mutual_revert[2]][1]
            reverted_rev_1 = revisions_ids_dict[mutual_revert[3]][1]
            revertant_rev_2 = revisions_ids_dict[mutual_revert[4]][1]
            reverted_rev_2 = revisions_ids_dict[mutual_revert[5]][1]

            revert_1 = (revertant_rev_1, reverted_rev_1)
            revert_2 = (revertant_rev_2, reverted_rev_2)
            mutual_revert = (revert_1, revert_2)

            info.mutual_reverts_list.append(mutual_revert)

        # 7º Load data in users_info_dict from users' table
        session_users = fetch_items_from_db(self.db_conn, "users", "id IN (", list(users_ids_set), in_clause=True)
        users_ids_dict: dict[str, str] = {}

        for user in session_users:
            username = user[2]
            site = user[3]
            is_registered = bool(user[4]) if user[4] is not None else None
            is_blocked = bool(user[5]) if user[5] is not None else None
            registration_date = datetime.strptime(user[6], self.__ISO_DATE_FORMAT) if user[6] else None
            edit_count = user[7]
            asn = user[8]
            asn_description = user[9]
            network_address = user[10]
            network_name = user[11]
            network_country = user[12]
            registrants_info = user[13]

            user_info = LocalUser(username, site, is_registered, is_blocked, registration_date, edit_count, asn,
                                  asn_description, network_address, network_name, network_country, registrants_info)

            Singleton().users_info_dict[username] = user_info
            users_ids_dict[user[1]] = username

        # 8º Update username field in revisions now that we have users info loaded
        for info in articles_with_edit_war_info_dict.values():
            for rev in info.revs_list:
                if rev.user:
                    rev.user = users_ids_dict[rev.user]

        # 9º Load data in _articles_with_edit_war_info_dict from reverted_user_pairs' table
        session_reverted_user_pairs = fetch_items_from_db(self.db_conn, "reverted_user_pairs",
                                                          "revertant_rev IN (", list(reverts_ids_dict.keys()),
                                                          in_clause=True)

        for reverted_user_pair in session_reverted_user_pairs:
            article, revertant_rev = revisions_ids_dict[reverted_user_pair[1]]
            _, reverted_rev = revisions_ids_dict[reverted_user_pair[2]]
            info = articles_with_edit_war_info_dict[article]
            reverts_list = info.reverts_list
            username = users_ids_dict[reverted_user_pair[3]]

            for revert in reverts_list:
                if revert[0].revid == revertant_rev.revid and revert[1].revid == reverted_rev.revid:
                    revert[2].add(username)

        # 10º Load data in _articles_with_edit_war_info_dict from mutual_reverters_activities' table
        session_mutual_reverters_activities = fetch_items_from_db(self.db_conn, "mutual_reverters_activities",
                                                                  "user IN (", list(users_ids_dict.keys()),
                                                                  in_clause=True,
                                                                  additional_where_clauses=["AND period IN ("],
                                                                  additional_where_values=[list(periods_ids_dict.keys())])

        for mutual_reverter_activity in session_mutual_reverters_activities:
            article = periods_ids_dict[mutual_reverter_activity[2]]
            info = articles_with_edit_war_info_dict[article]
            username = users_ids_dict[mutual_reverter_activity[1]]

            info.mutual_reverters_dict[username] = int(mutual_reverter_activity[3])

        # Only use input if a terminal is being used (automatic execution does not and could get blocked)
        if sys.stdin.isatty():
            input("Session successfully loaded (Enter to continue) ")


    def __save_session_menu(self) -> int:
        # Show stored sessions and ask user a name to save the new session
        session_id, session_overwritten = save_session_data(self.db_conn)

        print("\nStoring data in database, please wait... (WARNING: Do not close this window until process "
              "is finished or session data will be lost) ")

        # In case the session was previously stored and overwritten, data previously stored in this session and
        # eliminated during program execution must be eliminated from database too
        if session_overwritten:
            self._delete_remaining_session_data_from_db(str(session_id))

        # Save articles' information on articles' table
        articles_ids_dict: dict[int, int] = dict[int, int]()
        for article in self.articles_set:
            articles_ids_dict[article.pageid] = save_article_data(self.db_conn, article, session_id)

        # Save edit war information from analysed articles
        for article, info in Singleton().articles_with_edit_war_info_dict.items():

            # 1º Save article's info for those that are not already in the table
            if article not in self.articles_set:
                article_id = save_article_data(self.db_conn, article, session_id)
                articles_ids_dict[article.pageid] = article_id
            else:
                article_id = articles_ids_dict[article.pageid]

            # 2º Save period's info on edit_war_analysis_periods' table
            period_id = save_period_data(self.db_conn, articles_ids_dict, article, info)

            # 3º Save edit war over time values on edit_war_values' table
            for (value, date) in info.edit_war_over_time_list:
                save_edit_war_value(self.db_conn, period_id, date, value)

            # 4º Save users info on users' table
            users_ids_dict: dict[str, int] = dict[str, int]()

            for username, user_info in Singleton().users_info_dict.items():
                users_ids_dict[username] = save_user_data(self.db_conn, username, user_info)

            # 5º Save revisions and missing users info on their tables simultaneously
            revs_ids_dict: dict[int, int] = dict[int, int]()

            for i, local_rev in enumerate(info.revs_list):
                username = local_rev.user

                # If the user is not stored, we create a new entry only with the username and save the id in the dict.
                # (users_ids_dict is checked too, in order to not overwrite info stored in previous step and avoid
                # unnecessary iterations)
                if username and users_ids_dict.get(username) is None:
                    users_ids_dict[username] = save_user_data(self.db_conn, username, LocalUser(username))

                # Save revisions info on revisions' table
                rev_id = save_revision_data(self.db_conn, local_rev, users_ids_dict, article_id)
                revs_ids_dict[local_rev.revid] = rev_id

            # 6º Save reverts on reverts' table and its M:M relation with users (reverted_users) on
            # reverted_user_pairs' table
            for revertant_rev, reverted_rev, reverted_users_set in info.reverts_list:
                # Save reverts info on reverts' table
                revertant_rev_id = revs_ids_dict[revertant_rev.revid]
                reverted_rev_id = revs_ids_dict[reverted_rev.revid]

                save_revert_data(self.db_conn, revertant_rev_id, reverted_rev_id)

                # Save reverted_user_pairs info on reverted_user_pairs' table
                for username in reverted_users_set:
                   if username and users_ids_dict.get(username) is None:
                       users_ids_dict[username] = save_user_data(self.db_conn, username, LocalUser(username))

                   user_id = users_ids_dict[username]
                   save_reverted_user_pair_data(self.db_conn, revertant_rev_id, reverted_rev_id, user_id)

            # 7º Save mutual reverts on mutual_reverts' table
            for revert_1, revert_2 in info.mutual_reverts_list:
                save_mutual_revert_data(self.db_conn, revs_ids_dict, revert_1, revert_2)

            # 8º Save nº of mutual reverts of every user on this period for the analysed article on
            # mutual_reverters_activities' table
            for username, n_mutual_reverts in info.mutual_reverters_dict.items():
                if username:
                    user_id = users_ids_dict[username]
                    save_mutual_reverters_activity(self.db_conn, user_id, period_id, n_mutual_reverts)

        input("Session data successfully saved (Enter to continue) ")

        return session_id


    def _delete_remaining_session_data_from_db(self, session_id: str):
        # 1º Delete articles not included anymore
        session_articles = fetch_items_from_db(self.db_conn, "articles", "session = ?",
                                               [session_id])
        pageids_dict = {article[2]: (article[0], article[1]) for article in session_articles}
        articles_ids_dict = {}

        # Iterate pageids_dict keeping only those entries that are not in articles_set (those that must be deleted
        # from db)
        for article in self.articles_set:
            pageid = article.pageid
            if article.pageid in pageids_dict.keys():
                article_id = pageids_dict[pageid][1]
                articles_ids_dict[pageid] = article_id
                pageids_dict.pop(pageid)

        # Delete remaining entries
        for rowid, _ in pageids_dict.values():
            delete_from_db_table(self.db_conn, "articles", rowid)

        # 2º Delete revisions not included anymore
        session_revisions = fetch_items_from_db(self.db_conn, "revisions", "article IN (",
                                                list(articles_ids_dict.values()), in_clause=True)

        revids_dict = {rev[2]: (rev[0], rev[1]) for rev in session_revisions}

        # Iterate revids_dict keeping only those entries that are not in the revs_list of any of the articles loaded
        # (those that must be deleted from db)
        for article, article_info in Singleton().articles_with_edit_war_info_dict.items():
            for rev in article_info.revs_list:
                revid = rev.revid
                if revid in revids_dict.keys():
                    revids_dict.pop(revid)

        # Delete remaining entries
        for rowid, _ in revids_dict.values():
            delete_from_db_table(self.db_conn, "revisions", rowid)

        # 3º Delete edit_war_periods not included anymore
        session_periods = fetch_items_from_db(self.db_conn, "edit_war_analysis_periods", "article IN (",
                                              list(articles_ids_dict.values()), in_clause=True)

        periods_dict = {period[2]: (period[0], period[1], period[3], period[4], period[5]) for period in
                        session_periods}

        # Iterate periods_dict keeping only those entries that do not match the start and end dates or the notified
        # attribute saved for any of the articles loaded (those that must be deleted from db)
        for article, article_info in Singleton().articles_with_edit_war_info_dict.items():
            if articles_ids_dict.get(article.pageid):
                article_id = articles_ids_dict[article.pageid]
                if article_id in periods_dict.keys():
                    article_start_date = datetime_to_iso(article_info.start_date)
                    article_end_date = datetime_to_iso(article_info.end_date)
                    article_edit_war_notified = article_info.edit_war_notified
                    start_date = periods_dict[article_id][2]
                    end_date = periods_dict[article_id][3]
                    edit_war_notified = periods_dict[article_id][4]

                    if (article_start_date != start_date or article_end_date != end_date or
                            article_edit_war_notified != edit_war_notified):
                        periods_dict.pop(article_id)

        # Delete remaining entries
        for rowid, _, _, _, _ in periods_dict.values():
            delete_from_db_table(self.db_conn, "edit_war_analysis_periods", rowid)

        # 4º Delete users not included anymore
        # (In this case is different: users are only deleted if revisions in which they are authors have been deleted,
        # so, as non-included revisions have already been deleted, the db must be searched for users that are not
        # referenced by any revisions and delete them)
        delete_non_referenced_users(self.db_conn)


    def __delete_session_menu(self, stored_sessions_ids_list: list[int]) -> str:
        # Show sessions in database
        clear_terminal()
        print_delim_line("#")
        sessions = print_db_table(self.db_conn, "sessions")
        print(f'\nSessions stored: {len(sessions)}\n')
        print_delim_line("-")

        # Ask user about the session that wants to delete
        session_id = validate_idx_in_list(input("Select " + "ID of the session you want to delete from database "
                                                "(0 to return) "), stored_sessions_ids_list)

        if session_id != '0':
            # Delete session from database
            delete_from_db_table(self.db_conn, "sessions", int(session_id))
            # Update stored_sessions_ids_list
            stored_sessions_ids_list.remove(int(session_id))
            # Delete remaining data about deleted session (data that is not deleted in cascade once session is deleted)
            self._delete_remaining_session_data_from_db(session_id)

        clear_n_lines(5 + len(sessions) + 4 + Singleton().shared_dict["lines_to_remove"])

        return session_id


    @staticmethod
    def __query_session_menu() -> str:
        # Ask user about the query
        query = input("\nPlease, write your SELECT query: ")

        # Print menu
        clear_terminal()
        print_delim_line("#")

        # Create connection to temporal db session
        with sqlite_connection("file:temp_session.db?mode=ro", uri=True) as temp_db_conn:
            results = sanitize_and_execute_select(temp_db_conn, query) # Obtain results only after sanitizing the query

        # If results have been obtained, they are printed
        if results:
            description, rows = results
            print_query_contents(description, rows)

        print_delim_line("-")

        # Ask user if wants to keep querying, otherwise exit value ('0') is returned to exit from this menu
        question = "Do you want to try another query? "
        opt = '0' if not ask_yes_or_no_question(question) else ""

        return opt