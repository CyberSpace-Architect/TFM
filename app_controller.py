import heapq
import os
import pprint
import re
import logging
from typing import Tuple

import numpy as np

from local_revision import LocalRevision
from user_info import UserInfo

logging.getLogger("pywikibot.api").setLevel(logging.ERROR)

import pywikibot
import plotext as plt
from ipwhois import IPWhois
from datetime import datetime, timedelta, timezone
from sortedcontainers import SortedSet
from babel import Locale, localedata
from pywikibot import User
from sqlite3 import Connection


from article_edit_war_info import ArticleEditWarInfo
from wiki_crawler import WikiCrawler
from edit_war_detector import EditWarDetector
from utils import validate_idx, validate_date_format, clear_terminal, clear_n_lines, _shared_dict, \
    _articles_with_edit_war_info_dict, _users_info_dict, validate_idx_in_list
from db_utils import (reset_db, add_to_db_table, fetch_items_from_db, print_db_table, delete_from_db_table,
                      save_session_data, save_article_data, save_period_data, save_edit_war_value, save_user_data,
                      save_revision_data, save_revert_data, save_reverted_user_pair_data, save_mutual_revert_data,
                      save_mutual_reverters_activity)
from local_page import LocalPage


class AppController(object):
    CHOOSE_OPTION_MSG = "Select an option "
    INVALID_OPTION_MSG = "Invalid option, please select one of the list. (Enter to continue) "
    EMPTY_SET_MSG = "Search set empty, please first search some articles with option 1. (Enter to continue) "
    EMPTY_SESSIONS_MSG = "No sessions found in database, please save one first. (Enter to continue)"
    CONTINUE_MSG = "\nPress Enter to continue... "
    MENU_DELIMITER = "\n##########################################################################################\n"
    RESULTS_DELIMITER = "\n------------------------------------------------------------------------------------------\n"
    DATE_FORMAT = "%d/%m/%Y"

    articles_set: SortedSet[LocalPage] = None
    search_categories_set: SortedSet[LocalPage] = None
    search_articles_set: SortedSet[LocalPage] = None
    db_conn: Connection = None


    # def __init__(self):
    def __init__(self, conn):
        self.articles_set = SortedSet()
        self.search_categories_set = SortedSet()
        self.search_articles_set = SortedSet()
        self.db_conn = conn


    def exec(self):
        opt = ""

        while opt != '0':
            clear_terminal()
            print(self.MENU_DELIMITER)
            print("[1] Search articles by keywords")
            print("[2] Search articles related to one of the articles within the set")
            print("[3] Analyse presence of edit wars in articles within the set")
            print("[4] Analyse an article of the set in-depth")
            print("[5] Remove article from the set")
            print("[6] Load data from a previous session")
            print("[7] Delete saved session from database")
            print("[8] Reset database (clean all contents)")
            print("[0] Exit\n")

            opt = input(self.CHOOSE_OPTION_MSG)
            match opt:
                case '1':
                    # Ask user about search parameters
                    search, limit, language = self.__obtain_search_parameters()

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
                    opt_2 = ""
                    while opt_2 != '0':
                        opt_2 = self.__searched_articles_menu()

                case '2':
                    # Check articles set has at least 1 article to search related categories
                    if len(self.articles_set) == 0:
                        input(self.EMPTY_SET_MSG)
                        continue

                    # Show search set
                    WikiCrawler.print_pages(self.articles_set)
                    print(f'\nArticles in search set: {len(self.articles_set)}\n')

                    idx = input("Select nº of the article for which you want to search related categories ")
                    idx = int(validate_idx(idx, 0, len(self.articles_set)))

                    if idx == 0:
                        continue

                    # Extract related categories
                    pages = self.articles_set[idx-1].categories()

                    # Save results in SortedSet as PageGenerator only allows to iterate it once
                    for page in pages:
                        self.search_categories_set.add(LocalPage.init_with_page(page))

                    if len(self.search_categories_set) == 0:
                        clear_terminal()
                        input("No related categories for this article (Enter to continue) ")
                        continue

                    # New menu until user wants to return
                    opt_2 = ""
                    while opt_2 != '0':
                        opt_2 = self.__searched_categories_menu()

                case '3':
                    # Check articles set is not empty before calculating edit-war values
                    if len(self.articles_set) == 0:
                        input(self.EMPTY_SET_MSG)
                        continue

                    start_date = input("Specify start date (dd/mm/YYYY) to count revisions of searched articles "
                                       "(leave blank and press Enter to use past 30 days) ")
                    while start_date != "" and not validate_date_format(start_date, self.DATE_FORMAT):
                        start_date = input("Invalid date, please, introduce a valid one ")
                    if start_date == "":
                        start_date = (datetime.now() - timedelta(days=30))
                    else:
                        start_date = datetime.strptime(start_date, self.DATE_FORMAT)

                    end_date = input("Specify end date (dd/mm/YYYY) to count revisions of searched articles"
                                     " (leave blank and press Enter to use current date) ")
                    while end_date != "" and not validate_date_format(end_date, self.DATE_FORMAT):
                        end_date = input("Invalid date, please, introduce a valid one ")
                    if end_date == "":
                        end_date = datetime.now()
                    else:
                        end_date = datetime.strptime(end_date, self.DATE_FORMAT)

                    if start_date > end_date:
                        start_date, end_date = end_date, start_date

                    EditWarDetector.detect_edit_wars_in_set(self.articles_set, start_date, end_date)

                    print(self.RESULTS_DELIMITER)
                    print("Summary of results:\n")

                    EditWarDetector.print_pages_with_tags(_articles_with_edit_war_info_dict)

                    input(self.CONTINUE_MSG)

                case '4':
                    # Check articles set has at least 1 article to inspect
                    if len(self.articles_set) == 0:
                        input(self.EMPTY_SET_MSG)
                        continue

                    if len(_articles_with_edit_war_info_dict) == 0:
                        input('Please, select option 3 in main menu before requesting in-depth analysis '
                              'of an article (Enter to continue)')
                        continue

                    # New menu until user wants to return
                    opt_2 = ""
                    while opt_2 != '0':
                        opt_2 = self.__select_article_to_inspect_menu()

                case '5':
                    # Check articles set has at least 1 article to delete
                    if len(self.articles_set) == 0:
                        input(self.EMPTY_SET_MSG)
                        continue

                    opt_2 = ""
                    while opt_2 != '0':
                        opt_2 = self.delete_articles_menu()

                case '6':
                    # Load data from a previous session
                    sessions = print_db_table(self.db_conn, "sessions")
                    stored_sessions_ids = [0]
                    for session in sessions:
                        stored_sessions_ids.append(session[0])

                    opt_2 = validate_idx_in_list(input("\nSelect nº of the session you want to load (0 to return) "),
                                                 stored_sessions_ids)
                    session = None
                    if opt_2 != '0':
                        for session in sessions:
                            if session[0] == int(opt_2):
                                break

                        self.load_session_data_menu(session)

                case '7':
                    # Delete a session from the database
                    sessions = fetch_items_from_db(self.db_conn, "sessions")

                    if len(sessions) == 0:
                        input(self.EMPTY_SESSIONS_MSG)
                        continue

                    opt_2 = ""
                    while opt_2 != '0':
                        opt_2 = self.delete_session_menu()

                case '8':
                    # Ask user to confirm the action to avoid miss clicks
                    confirmation_msg = input("Resetting the database will delete all previous information stored "
                                             "including all previous sessions, are you sure you want to reset the it? ")

                    while confirmation_msg not in {"y", "yes", "n", "no"}:
                        confirmation_msg = re.sub(r'\s+', '', input("Invalid response, please write y or yes "
                                                                    "if you want to save it, n or no otherwise ").lower())
                    if confirmation_msg in {"n", "no"}:
                        continue
                    else:
                        # Delete database and create a new one
                        reset_db(self.db_conn)

                case '0': # Exit
                    self.articles_set.clear()
                    want_to_save = re.sub(r'\s+', '', input("Data not saved, do you want to save it "
                                                               "before exit? ").lower())

                    while want_to_save not in {"y", "yes", "n", "no"}:
                        want_to_save = re.sub(r'\s+', '', input("Invalid response, please write y or yes if "
                                                                    "you want to save it, n or no otherwise ").lower())
                        clear_n_lines(1)
                    if want_to_save in {"y", "yes"}:
                        self.save_session_menu()

                    clear_terminal()

                case _:
                    input(self.INVALID_OPTION_MSG)


    @staticmethod
    def __obtain_search_parameters() -> [str, int, str]:
        # Search keywords
        search = input("What do you want to search for? ")

        while search == "":
            search = input("Search field cannot be empty, please try again ")

        # Max nº of articles to search
        limit = input("How many pages do you want to search at most? (Enter for no limit) ")

        while limit != "" and (not limit.isdigit() or int(limit) <= 0):
            limit = input("Invalid limit, introduce a value higher than zero ")

        limit = None if limit == "" else int(limit)

        # Search language
        language = Locale(WikiCrawler.language_code).get_display_name('en')
        change_language = re.sub(r'\s+', '', input(f'Language selected for search: {language}, do you want '
                                                               f'to change it? ').lower())

        while change_language not in {"y", "yes", "n", "no"}:
            change_language = re.sub(r'\s+', '', input("Invalid response, please write y or yes if you want"
                                                                   " to change it, n or no otherwise ").lower())

        if change_language in {"y", "yes"}:
            language_codes = sorted(pywikibot.family.Family.load("wikipedia").langs.keys())

            idx = 0
            language_list = []
            while idx < len(language_codes):
                code = language_codes[idx]
                if localedata.exists(code):
                    language = Locale(code).get_display_name('en')  # Name in English
                    print(f'[{idx+1}] {language}')
                    language_list.append(language)
                    idx += 1
                else:
                    language_codes.pop(idx)

            idx = input("\nFrom the list above, please, select the nº of the Wiki's language in which you want to search ")
            idx = int(validate_idx(idx, 0, len(language_codes) - 1))

            WikiCrawler.set_language_code(language_codes[idx-1])
            language = Locale(language_codes[idx]).get_display_name('en')

        return search, limit, language


    def __searched_articles_menu(self) -> str:
        clear_terminal()
        print(self.MENU_DELIMITER)

        # Show search results
        WikiCrawler.print_pages(self.search_articles_set)
        print(f'\nResults found: {len(self.search_articles_set)}')

        print(self.RESULTS_DELIMITER)
        idx = ""

        while idx != '0':
            if len(self.articles_set) == 0:
                print("No articles added yet\n")
                _shared_dict["lines_to_remove"] = _shared_dict.get("lines_to_remove", 0) + 2
            else:
                WikiCrawler.print_pages(self.articles_set, will_remove_lines=True)
                print("\nArticles added: " + str(len(self.articles_set)) + "\n")
                _shared_dict["lines_to_remove"] = _shared_dict.get("lines_to_remove", 0) + 4

        # Show options
            idx = validate_idx(input("Select nº of the article you want to add to search set (0 to return) "),
                                     0, len(self.search_articles_set))
            _shared_dict["lines_to_remove"] = _shared_dict.get("lines_to_remove", 0) + 1

            if idx != '0':
                # Add article to the set that the application works with
                local_page = self.search_articles_set[int(idx)-1]
                self.articles_set.add(local_page)

                clear_n_lines(_shared_dict.get("lines_to_remove", 0))
            else:
                self.search_articles_set.clear()

            _shared_dict["lines_to_remove"] = 0

        return idx


    def __searched_categories_menu(self):
        clear_terminal()
        print(self.MENU_DELIMITER)

        # Show search results
        WikiCrawler.print_pages(self.search_categories_set)
        print(f'\nResults found: {len(self.search_categories_set)}\n')

        # Show options
        idx = ""
        while idx != '0':
            idx = validate_idx(input("Select nº of the category for which you want to search related articles (0 to return) "),
                           0, len(self.search_categories_set))

            if idx != '0':
                limit = input("How many pages do you want to search at most? (Enter for no limit) ")

                while limit != "" and (not limit.isdigit() or int(limit) <= 0):
                    limit = input("Invalid limit, introduce a value higher than zero ")

                limit = None if limit == "" else int(limit)

                pages = WikiCrawler.crawl_articles((self.search_categories_set[int(idx)-1]).title, search_limit=limit, search_type=1)

                for page in pages:
                    self.search_articles_set.add(LocalPage.init_with_page(page))

                if len(self.search_articles_set) == 0:
                    input("Search yielded no results try another category (Enter to continue) ")
                else:
                    idx_2 = ""
                    while idx_2 != '0':
                        idx_2 = self.__searched_articles_menu()

                    # Print menu contents again
                    clear_terminal()
                    print(self.MENU_DELIMITER)
                    WikiCrawler.print_pages(self.search_categories_set)
                    print(f'\nResults found: {len(self.search_categories_set)}\n')
            else:
                self.search_categories_set.clear()

        return idx


    def __select_article_to_inspect_menu(self):
        idx = ""
        while idx != '0':
            clear_terminal()
            print(self.MENU_DELIMITER)

            # Show articles set
            EditWarDetector.print_pages_with_tags(_articles_with_edit_war_info_dict)
            print(f'\nArticles in search set: {len(self.articles_set)}\n')
            idx = validate_idx(input("Select nº of the article you want to inspect (0 to return) "),
                               0, len(self.articles_set))

            if idx == '0':
                return idx

            # Calculate and show edit war info
            local_page = self.articles_set[int(idx) - 1]

            opt = ""
            while opt != '0':
                opt = self.inspect_article_in_depth_menu(local_page)

        return idx


    def inspect_article_in_depth_menu(self, local_page: LocalPage):
        opt = ""
        while opt != '0':
            clear_terminal()
            print(self.MENU_DELIMITER)
            print(f'Selected article: {local_page.title} ({local_page.full_url()})')

            print(self.RESULTS_DELIMITER)
            print("Article info:")
            info:ArticleEditWarInfo = _articles_with_edit_war_info_dict[local_page]

            # Conflict severity (edit war value for the whole time period)
            edit_war_value = info.edit_war_over_time_list[-1][0]
            print(f'\n\t- Conflict severity (edit war value, higher than '
                  f'{EditWarDetector.EDIT_WAR_THRESHOLD} is considered edit war): {edit_war_value}')

            # Conflict's size (nº of users mutually reverting each other)
            n_mutual_reverters = len(info.mutual_reverters_dict)
            print(f'\n\t- Conflict\'s size (nº of users mutually reverting each other): {n_mutual_reverters}')

            # Conflict's temporal evolution
            self.__print_conflict_evolution(info)

            # Fighting editors ordered from higher to lower activity (based on the nº of mutual reverts made)
            self.__print_ordered_mutual_reverters(info)

            # Top 10 most reverted revisions, along with the number of reverts
            reverted_revisions_dict = self.__print_most_reverted_revisions(info)

            print(self.RESULTS_DELIMITER)
            print("[1] Inspect article's history page")
            print("[2] Inspect article's discussion page")
            print("[3] Inspect a user from the list")
            print("[4] Inspect a revision from the list")
            print("[0] Return to articles' list\n")

            opt = input(self.CHOOSE_OPTION_MSG)
            match opt:
                case '1':
                    clear_terminal()
                    print(self.MENU_DELIMITER)
                    WikiCrawler.print_pages({local_page}, time_range=(info.start_date, info.end_date),
                                            history_changes=True)
                    input(self.CONTINUE_MSG)
                    opt = ""
                case '2':
                    clear_terminal()
                    print(self.MENU_DELIMITER)
                    WikiCrawler.print_pages({local_page}, time_range=[info.start_date, info.end_date],
                                            discussion_changes=True)
                    input(self.CONTINUE_MSG)
                    opt = ""
                case '3':
                    opt = self.__inspect_user_menu(info)
                case '4':
                    opt = self.__inspect_revision_menu(info, reverted_revisions_dict)
                case '0':
                    continue
                case _:
                    input(self.INVALID_OPTION_MSG)

        return opt


    @staticmethod
    def __print_conflict_evolution(info: ArticleEditWarInfo):
        print("\n\t- Conflict's temporal evolution (graph with edit war values over time): ")
        intervals = ArticleEditWarInfo.split_time_interval(info.start_date, info.end_date)
        xvals, yvals = [], []

        if len(info.edit_war_over_time_list) > 1:
            for i, interval in enumerate(intervals):
                xvals.append(interval.strftime("%d/%m/%Y"))
                yvals.append(int(info.edit_war_over_time_list[i][0]))
        else:
            print("\n\t==> Calculating edit war values to plot...\n")

            # Calculate edit war values for each of the intervals. To do so, the revs_list of each interval has to
            # be created incrementally, except for the final interval which is the complete time range (previously
            # calculated)
            revs_list = []
            last_rev_idx = 0
            for i, interval in enumerate(intervals):
                if i == len(intervals)-1:
                    edit_war_value = info.edit_war_over_time_list[-1][0]
                else:
                    interval_surpassed = False
                    while not interval_surpassed and last_rev_idx < len(info.revs_list):
                        local_rev = info.revs_list[last_rev_idx]
                        rev_date = local_rev.timestamp

                        if datetime.strptime(rev_date, "%Y-%m-%dT%H:%M:%SZ") < interval:
                            revs_list.append(local_rev)
                            last_rev_idx += 1
                        else:
                            interval_surpassed = True

                    _, _, _, edit_war_value = EditWarDetector.is_article_in_edit_war(revs_list)
                    info.edit_war_over_time_list.insert(0, (edit_war_value, interval))

                xvals.append(interval.strftime("%d/%m/%Y"))
                yvals.append(int(edit_war_value))

                clear_n_lines(1)
                print(f'\t\tIntervals with edit war value calculated {i+1}/{len(intervals)}')

            clear_n_lines(3)

        print("\n")

        # Clear previous graph configuration
        plt.clear_figure()

        # Set graph's dimensions
        size = os.get_terminal_size()
        width = size.columns
        height = size.lines
        plt.plot_size(width=width, height=min(60, height - 5))

        # Prepare and assign Y axis values
        min_y = min(yvals)
        max_y = max(yvals)
        yticks = list(np.linspace(min_y, max_y, 10))
        yticks = [int(round(t)) for t in yticks]
        yticks = sorted(set(yticks))  # Delete duplicates
        plt.yticks(yticks)

        # Assign X axis values
        plt.xticks(xvals)

        # Set graph's visual configuration
        plt.canvas_color("black")
        plt.axes_color("black")
        plt.ticks_color("white")
        plt.title("CONFLICT'S TEMPORAL EVOLUTION")
        plt.xlabel("TIME")
        plt.ylabel('EDIT WAR VALUES')

        # Print graph
        plt.bar(xvals, yvals, color="blue")
        plt.show()


    @staticmethod
    def __print_ordered_mutual_reverters(info):
        for mutual_reverts_tuple in info._mutual_reverts_list:
            user_i = mutual_reverts_tuple[0][1].user
            user_j = mutual_reverts_tuple[1][1].user
            info.mutual_reverters_dict[user_i] = info.mutual_reverters_dict.get(user_i, 0) + 1
            info.mutual_reverters_dict[user_j] = info.mutual_reverters_dict.get(user_j, 0) + 1

        # Order resulting dict
        info.mutual_reverters_dict = dict(sorted(info.mutual_reverters_dict.items(), key=lambda item: item[1], reverse=True))

        print("\n\t- Fighting editors ordered from higher to lower conflicting activity (nº of mutual reverts made): ")
        print("\n\t\tRANK --> EDITOR --> Nº OF MUTUAL REVERTS")
        for i, (user_i, edits) in enumerate(info.mutual_reverters_dict.items()):
            print(f'\t\t{i + 1} --> {user_i} --> {edits}')


    @staticmethod
    def __print_most_reverted_revisions(info):
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
            print(f'\t\t{i+1} --> [{rev_id}, {rev.timestamp}, {rev.user}] '
                  f'--> {len(reverts_list)}')

        return reverted_revisions_dict


    def __inspect_user_menu(self, info):
        user_name = input("Please indicate the name of the user you want to inspect ")

        while not info.mutual_reverters_dict.get(user_name):
            user_name = input("Name not found on the list, please try again ")

        if _users_info_dict.get(user_name) and _users_info_dict[user_name].is_registered is not None:
            user_info = _users_info_dict[user_name]

            clear_terminal()
            print(self.MENU_DELIMITER)
            print(f'Selected user: {user_info.username}')
            print(self.RESULTS_DELIMITER)
            print("User info:")
            print(f'\n\t- Username: {user_info.username} \n\n\t- Is registered?: {user_info.is_registered} '
                  f'\n\n\t- Is blocked?: {user_info.is_blocked} \n\n\t- Registration date: {str(user_info.registration_date)} '
                  f'\n\n\t- Nº of global user edits (0 for anonymous users, ie. IP) {user_info.edit_count}')

            print(f'\n\t- ASN: {user_info.asn} ({user_info.asn_description})')
            print(f'\n\t- Network: {user_info.network_address} ({user_info.network_name}) '
                  f'\n\n\t- Country: {user_info.network_country}' f'\n\n\t- Registrants info: {user_info.registrants_info}')
        else:
            user = User(WikiCrawler.site, user_name)

            username = user.username
            is_registered = user.isRegistered()
            is_blocked = user.is_blocked()
            registration = user.registration()
            edit_count = user.editCount()

            user_info = UserInfo(username, is_registered, is_blocked, registration, edit_count)

            clear_terminal()
            print(self.MENU_DELIMITER)
            print(f'Selected user: {username}')
            print(self.RESULTS_DELIMITER)
            print("User info:")
            print(f'\n\t- Username: {username} \n\n\t- Is registered?: {is_registered} '
                  f'\n\n\t- Is blocked?: {is_blocked} \n\n\t- Registration date: {registration} '
                  f'\n\n\t- Nº of global user edits (0 for anonymous users, ie. IP) {edit_count}')

            ipv4_pattern = r'^((25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.|$)){4}$'
            ipv6_pattern = r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'
            if re.fullmatch(ipv4_pattern, username) or re.fullmatch(ipv6_pattern, username):
                whois = IPWhois(user.username)
                result = whois.lookup_rdap()

                network = result.get("network", {})
                user_info.asn = result["asn"]
                user_info.asn_description = result["asn_description"]
                user_info.network_address = network.get("handle", "Info not available")
                user_info.network_name = network.get("name", "Info not available")
                user_info.network_country = network.get("country", "Info not available")

                print(f'\n\t- ASN: {user_info.asn} ({user_info.asn_description})')
                print(f'\n\t- Network: {user_info.network_address} ({user_info.network_name}) '
                      f'\n\n\t- Country: {user_info.network_country}')

                objects = result.get("objects", {})
                registrants_dict: dict[str, dict] = {}
                for object_name, object_info in objects.items():
                    if object_info.get("roles", []) == ["registrant"]:
                        registrants_dict[object_name] = object_info

                if len(registrants_dict) > 0:
                    print("\n\t- Registrants info: ")

                    for object_name, object_info in registrants_dict.items():
                        print(f'\n\t{object_name}: ')
                        formatted_info = pprint.pformat(object_info, indent=2)
                        tabbed_info = '\n'.join('\t' + line for line in formatted_info.splitlines())
                        user_info.registrants_info = tabbed_info
                        print(tabbed_info)

                    user_info.registrants_info = tabbed_info

            _users_info_dict[user.username] = user_info

        input(self.CONTINUE_MSG)


    def __inspect_revision_menu(self, info, reverted_revisions_dict):
        rev_id = input("Please indicate the ID of the revision you want to inspect ")

        selected_local_rev = None
        while selected_local_rev is None:
            for local_rev in info.revs_list:
                if str(local_rev.revid) == rev_id:
                    selected_local_rev = local_rev
                    break
            if selected_local_rev is None:
                input("ID not found on article's history page, please try a different one ")

        clear_terminal()
        print(self.MENU_DELIMITER)
        print(f'Selected revision: {str(selected_local_rev.revid)}')
        print(self.RESULTS_DELIMITER)
        print("Revision info:")
        print(f'\n\t- ID: {str(selected_local_rev.revid)} \n\n\t- Timestamp: {selected_local_rev.timestamp} '
              f'\n\n\t- Author: {selected_local_rev.user} '
              f'\n\n\t- Comment: {selected_local_rev.comment}')

        print("\n\t- List of reverts made to this revision: ")
        reverts_list = reverted_revisions_dict[int(rev_id)][1]
        print("\n\t\tREV ID, TIMESTAMP, USER")
        for local_rev in reverts_list:
            print(f'\n\t\t{str(local_rev.revid)}, {local_rev.timestamp}, {local_rev.user}')

        if not selected_local_rev.text:
            rev_date = datetime.strptime(selected_local_rev.timestamp, "%Y-%m-%dT%H:%M:%SZ")
            fam, code = info.article.site.split(":", 1)
            site = pywikibot.Site(code, fam)

            if not info.article.page:
                info.article.page = next(site.load_pages_from_pageids([info.article.pageid]))

            local_rev_list = WikiCrawler.get_full_revisions_in_range(site, info.article.page, rev_date, rev_date,
                                                                     include_text = True)

            contents = local_rev_list[0].revision['slots']['main'].get('*', None)
        else:
            contents = selected_local_rev.text

        if contents is None:
            print("\n\t- Contents: Not publicly available (deleted or protected)")
        else:
            print(f'\n\t- Contents: \n\n{contents}')
            selected_local_rev.text = contents

        input(self.CONTINUE_MSG)


    def delete_articles_menu(self):
        clear_terminal()
        print(self.MENU_DELIMITER)

        # Show articles in set
        WikiCrawler.print_pages(self.articles_set)
        print(f'\nArticles in search set: {len(self.articles_set)}\n')

        # Show options
        idx = validate_idx(input("Select nº of the article you want to delete from search set (0 to return) "),
                           0, len(self.articles_set))
        if idx != '0':
            # If edit war analysis option has not been used yet
            if len(_articles_with_edit_war_info_dict) != 0:
                _articles_with_edit_war_info_dict.pop(self.articles_set[int(idx)-1])

            self.articles_set.pop(int(idx)-1)

        return idx


    def load_session_data_menu(self, session_data: Tuple):
        session_id = session_data[0]

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

        periods_ids_dict: dict[str, LocalPage] = {}
        for period in session_periods:
            article = articles_ids_dict[period[2]]
            start_date = datetime.strptime(period[3], "%Y-%m-%dT%H:%M:%SZ") if period[2] else None
            end_date = datetime.strptime(period[4], "%Y-%m-%dT%H:%M:%SZ") if period[2] else None

            article_info = ArticleEditWarInfo(article, start_date, end_date)

            _articles_with_edit_war_info_dict[article] = article_info
            periods_ids_dict[period[1]] = article

        # 3º Load data in _articles_with_edit_war_info_dict from edit_war_values' table
        session_values = fetch_items_from_db(self.db_conn, "edit_war_values", "period IN (",
                                              list(periods_ids_dict.keys()), in_clause=True)

        for edit_war_value in session_values:
            article = periods_ids_dict[edit_war_value[1]]
            info:ArticleEditWarInfo = _articles_with_edit_war_info_dict[article]
            date = datetime.strptime(edit_war_value[2], "%Y-%m-%dT%H:%M:%SZ") if edit_war_value[2] else None
            value = edit_war_value[3]

            info.edit_war_over_time_list.append((value, date))


        # 4º Load data in _articles_with_edit_war_info_dict from revisions' table
        session_revisions = fetch_items_from_db(self.db_conn, "revisions", "article IN (",
                                             list(articles_ids_dict.keys()), in_clause=True)
        revisions_ids_dict: dict[str, (LocalPage, LocalRevision)] = {}
        users_ids_set = set[str]()

        for rev in session_revisions:
            article = articles_ids_dict[rev[3]]
            info: ArticleEditWarInfo = _articles_with_edit_war_info_dict[article]
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

        # Load data in _articles_with_edit_war_info_dict from reverts' table
        session_reverts = fetch_items_from_db(self.db_conn, "reverts", "revertant_rev IN (",
                                                list(revisions_ids_dict.keys()), in_clause=True)
        reverts_ids_dict: dict[str, (LocalPage, LocalRevision)] = {}

        for session_revert in session_reverts:
            article, rev = revisions_ids_dict[session_revert[1]]
            info: ArticleEditWarInfo = _articles_with_edit_war_info_dict[article]
            revertant_rev = revisions_ids_dict[session_revert[1]][1]
            reverted_rev = revisions_ids_dict[session_revert[2]][1]
            reverted_users_set = set[str]()

            revert = (revertant_rev, reverted_rev, reverted_users_set)

            info.reverts_list.append(revert)
            reverts_ids_dict[session_revert[1]] = (article, rev)

        # Load data in _articles_with_edit_war_info_dict from mutual_reverts' table
        session_mutual_reverts = fetch_items_from_db(self.db_conn, "mutual_reverts", "revertant_rev_1 "
                                                     "IN (", list(reverts_ids_dict.keys()), in_clause=True)

        for mutual_revert in session_mutual_reverts:
            article, rev = reverts_ids_dict[mutual_revert[2]]
            info: ArticleEditWarInfo = _articles_with_edit_war_info_dict[article]
            revertant_rev_1 = revisions_ids_dict[mutual_revert[2]][1]
            reverted_rev_1 = revisions_ids_dict[mutual_revert[3]][1]
            revertant_rev_2 = revisions_ids_dict[mutual_revert[4]][1]
            reverted_rev_2 = revisions_ids_dict[mutual_revert[5]][1]

            revert_1 = (revertant_rev_1, reverted_rev_1)
            revert_2 = (revertant_rev_2, reverted_rev_2)
            mutual_revert = (revert_1, revert_2)

            info.mutual_reverts_list.append(mutual_revert)

        # Load data in users_info_dict from users' table
        session_users = fetch_items_from_db(self.db_conn, "users", "id IN (", list(users_ids_set), in_clause=True)
        users_ids_dict: dict[str, str] = {}

        for user in session_users:
            username = user[2]
            is_registered = user[3]
            is_blocked = user[4]
            registration_date = datetime.strptime(user[5], "%Y-%m-%dT%H:%M:%SZ") if user[5] else None
            edit_count = user[6]
            asn = user[7]
            asn_description = user[8]
            network_address = user[9]
            network_name = user[10]
            network_country = user[11]
            registrants_info = user[12]

            user_info = UserInfo(username, is_registered, is_blocked, registration_date, edit_count, asn,
                                 asn_description, network_address, network_name, network_country, registrants_info)

            _users_info_dict[username] = user_info
            users_ids_dict[user[1]] = username

        # Update username field in revisions now that we have users info loaded
        for info in _articles_with_edit_war_info_dict.values():
            for rev in info.revs_list:
                if rev.user:
                    rev.user = users_ids_dict[rev.user]

        # Load data in _articles_with_edit_war_info_dict from reverted_user_pairs' table
        session_reverted_user_pairs = fetch_items_from_db(self.db_conn, "reverted_user_pairs",
                                                          "revertant_rev IN (", list(reverts_ids_dict.keys()),
                                                          in_clause=True)

        for reverted_user_pair in session_reverted_user_pairs:
            article, revertant_rev = revisions_ids_dict[reverted_user_pair[1]]
            _, reverted_rev = revisions_ids_dict[reverted_user_pair[2]]
            info: ArticleEditWarInfo = _articles_with_edit_war_info_dict[article]
            reverts_list = info.reverts_list
            username = users_ids_dict[reverted_user_pair[3]]

            for revert in reverts_list:
                if revert[0].revid == revertant_rev.revid and revert[1].revid == reverted_rev.revid:
                    revert[2].add(username)

        # Load data in _articles_with_edit_war_info_dict from mutual_reverters_activities' table
        session_mutual_reverters_activities = fetch_items_from_db(self.db_conn, "mutual_reverters_activities",
                                                                  "user IN (", list(users_ids_dict.keys()),
                                                                  in_clause=True,
                                                                  additional_where_clauses=["AND period IN ("],
                                                                  additional_where_values=[list(periods_ids_dict.keys())])

        for mutual_reverter_activity in session_mutual_reverters_activities:
            article = periods_ids_dict[mutual_reverter_activity[2]]
            info: ArticleEditWarInfo = _articles_with_edit_war_info_dict[article]
            username = users_ids_dict[mutual_reverter_activity[1]]

            info.mutual_reverters_dict[username] = int(mutual_reverter_activity[3])

        input("Session successfully loaded (Enter to continue) ")


    def delete_session_menu(self):
        # Show sessions in database
        sessions = print_db_table(self.db_conn, "sessions")
        print(f'\nSessions stored: {len(sessions)}\n')

        # Show options
        idx = input("Select nº of the session you want to delete from database (0 to return) ")

        if idx != '0':
            delete_from_db_table(self.db_conn, "sessions", int(idx))

        clear_n_lines(5 + len(sessions) + 4 + _shared_dict["lines_to_remove"])

        return idx


    def save_session_menu(self):
        # Show stored sessions and ask user a name to save the new session
        session_id = save_session_data(self.db_conn)

        print("\nStoring data in database, please wait... (WARNING: Do not close this window until process "
              "is finished or session data will be lost) ")

        # Save articles' information on articles' table
        articles_ids_dict: dict[(int, int)] = dict[(int, int)]()
        for article in self.articles_set:
            articles_ids_dict[article.pageid] = save_article_data(self.db_conn, article, session_id)

        # Save edit war information from analysed articles (Its mostly the same code as save_articles_data() but can't
        # be reused for this case)
        for article, info in _articles_with_edit_war_info_dict.items():
            info:ArticleEditWarInfo

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
            for username, user_info in _users_info_dict.items():
                if username and user_info is not None:
                    users_ids_dict[username] = save_user_data(self.db_conn, username, user_info)

            # 5º Save revisions and missing users info on their tables simultaneously
            revs_ids_dict: dict[int, int] = dict[int, int]()
            column_names = ("username, is_registered, is_blocked, registration_date, edit_count, asn, asn_description, "
                            "network_address, network_name, network_country, registrants_info")
            where_clause = "username=?"

            for i, local_rev in enumerate(info.revs_list):
                where_values = [local_rev.user]
                item = (local_rev.user, None, None, None, None, None, None, None, None, None, None)

                # If the user is not stored, we create a new entry only with the username
                if local_rev.user:
                    user_entry = fetch_items_from_db(self.db_conn, "users", where_clause, where_values)

                    if not user_entry:
                        users_ids_dict[local_rev.user] = add_to_db_table(self.db_conn, "users", column_names, item, return_id=True)
                    else:
                        # If user is already stored, we must save this info in the dictionary
                        users_ids_dict[user_entry[0][2]] = user_entry[0][0]

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
                    if username != "":
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

        input("Session data successfully saved, have a good day! (Enter to exit)")