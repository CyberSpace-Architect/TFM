import heapq
import os
import pprint
import re
import pywikibot
import plotext as plt
from ipwhois import IPWhois

from datetime import datetime, timedelta
from sortedcontainers import SortedSet
from babel import Locale, localedata
from pywikibot import User

from article_edit_war_info import ArticleEditWarInfo
from wiki_crawler import WikiCrawler
from edit_war_detector import EditWarDetector
#from edit_war_detector_texto import EditWarDetector
#from edit_war_detector_ppdeep import EditWarDetector
from utils import validate_idx, validate_date_format, clear_terminal, clear_n_lines, _shared_dict, _articles_with_edit_war_info_dict

import logging
logging.getLogger("pywikibot.api").setLevel(logging.ERROR)


class AppController(object):
    CHOOSE_OPTION_MSG = "Select an option "
    INVALID_OPTION_MSG = "Invalid option, please select one of the list. (Enter to continue) "
    EMPTY_SET_MSG = "Search set empty, please first search some articles with option 1. (Enter to continue) "
    CONTINUE_MSG = "\nPress Enter to continue... "
    MENU_DELIMITER = "\n##########################################################################################\n"
    RESULTS_DELIMITER = "\n------------------------------------------------------------------------------------------\n"
    DATE_FORMAT = "%d/%m/%Y"

    articles_set: SortedSet[pywikibot.Page] = None
    search_categories_set: SortedSet[pywikibot.Page] = None
    search_articles_set: SortedSet[pywikibot.Page] = None


    def __init__(self):
        self.articles_set = SortedSet()
        self.search_categories_set = SortedSet()
        self.search_articles_set = SortedSet()


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
            print("[0] Exit\n")

            opt = input(self.CHOOSE_OPTION_MSG)
            match opt:
                case '1':
                    # Ask user about search parameters
                    search, limit, language = self.obtain_search_parameters()

                    # Crawl wikipedia for articles
                    pages = WikiCrawler.crawl_articles(search, search_limit=limit, search_type=0)

                    # Save results in SortedSet as PageGenerator only allows to iterate it once
                    for page in pages:
                        self.search_articles_set.add(page)

                    # Inform user and return to main menu if search yielded no results
                    if len(self.search_articles_set) == 0:
                        input("Search yielded no results (Enter to continue) ")
                        continue

                    # New menu until user wants to return
                    opt_2 = ""
                    while opt_2 != '0':
                        opt_2 = self.searched_articles_menu()

                case '2':
                    # Check articles set has at least 1 article to search related categories
                    if len(self.articles_set) == 0:
                        input(self.EMPTY_SET_MSG)
                        continue

                    # Show search set
                    WikiCrawler.print_pages(self.articles_set)
                    print(f'\nArticles in search set: {len(self.articles_set)}\n')

                    idx = input("Select index of the article for which you want to search related categories ")
                    idx = int(validate_idx(idx, 0, len(self.articles_set)))

                    if idx == 0:
                        continue

                    # Extract related categories
                    pages = self.articles_set[idx-1].categories()

                    # Save results in SortedSet as PageGenerator only allows to iterate it once
                    for page in pages:
                        self.search_categories_set.add(page)

                    if len(self.search_categories_set) == 0:
                        clear_terminal()
                        input("No related categories for this article (Enter to continue) ")
                        continue

                    # New menu until user wants to return
                    opt_2 = ""
                    while opt_2 != '0':
                        opt_2 = self.searched_categories_menu()

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
                        opt_2 = self.select_article_to_inspect_menu()

                case '5':
                    # Check articles set has at least 1 article to delete
                    if len(self.articles_set) == 0:
                        input(self.EMPTY_SET_MSG)
                        continue

                    opt_2 = ""
                    while opt_2 != '0':
                        opt_2 = self.delete_articles_menu()

                case '0': # Exit
                    self.articles_set.clear()
                    clear_terminal()

                case _:
                    input(self.INVALID_OPTION_MSG)


    def obtain_search_parameters(self) -> [str, int, str]:
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


    def select_article_to_inspect_menu(self):
        idx = ""
        while idx != '0':
            clear_terminal()
            print(self.MENU_DELIMITER)

            # Show articles set
            EditWarDetector.print_pages_with_tags(_articles_with_edit_war_info_dict)
            print(f'\nArticles in search set: {len(self.articles_set)}\n')
            idx = validate_idx(input("Select index of the article you want to inspect (0 to return) "),
                               0, len(self.articles_set))

            if idx == '0':
                return idx

            # Calculate and show edit war info
            article = self.articles_set[int(idx)-1]

            opt = ""
            while opt != '0':
                opt = self.inspect_article_in_depth_menu(article)

        return idx


    def inspect_article_in_depth_menu(self, article):
        opt = ""
        while opt != '0':
            clear_terminal()
            print(self.MENU_DELIMITER)
            print(f'Selected article: {article.title()} ({article.full_url()})')

            print(self.RESULTS_DELIMITER)
            print("Article info:")
            info = _articles_with_edit_war_info_dict[article]

            # Conflict severity (edit war value for the whole time period)
            edit_war_value = info.edit_war_over_time_list[len(info.edit_war_over_time_list)-1]
            print(f'\n\t- Conflict severity (edit war value, higher than '
                  f'{EditWarDetector.EDIT_WAR_THRESHOLD} is considered edit war): {edit_war_value}')

            # Conflict's size (nº of users mutually reverting each other
            n_mutual_reversers = len(info.mutual_reversers_dict)
            print(f'\n\t- Conflict\'s size (nº of users mutually reverting each other): {n_mutual_reversers}')

            # Conflict's temporal evolution
            self.print_conflict_evolution(article, info)

            # Fighting editors ordered from higher to lower activity (based on the nº of mutual reverts made)
            ordered_fighting_editors_dict = self.print_fighting_editors(info)

            # Top 10 most reverted revisions, along with the number of reverts
            reverted_revisions_dict = self.print_most_reverted_revisions(info)

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
                    WikiCrawler.print_pages({article}, time_range=[info.start_date, info.end_date],
                                            history_changes=True)
                    input(self.CONTINUE_MSG)
                    opt = ""
                case '2':
                    clear_terminal()
                    print(self.MENU_DELIMITER)
                    WikiCrawler.print_pages({article}, time_range=[info.start_date, info.end_date],
                                            discussion_changes=True)
                    input(self.CONTINUE_MSG)
                    opt = ""
                case '3':
                    opt = self.__inspect_user_menu(ordered_fighting_editors_dict)
                case '4':
                    opt = self.__inspect_revision_menu(info, reverted_revisions_dict)
                case '0':
                    continue
                case _:
                    input(self.INVALID_OPTION_MSG)

        return opt


    def print_conflict_evolution(self, article, info):
        print("\n\t- Conflict's temporal evolution (graph with edit war values over time): ")
        intervals = ArticleEditWarInfo.split_time_interval(info.start_date, info.end_date)
        xvals, yvals = [], []

        if len(info.edit_war_over_time_list) > 1:
            for i, interval in enumerate(intervals):
                xvals.append(interval.strftime("%d/%m/%y"))
                yvals.append(int(info.edit_war_over_time_list[i]))
        else:
            print("\n\t==> Calculating edit war values to plot...\n")

            for i, interval in enumerate(intervals):
                if i == len(intervals)-1:
                    edit_war_value = info.edit_war_over_time_list[-1]
                else:
                    _, edit_war_value = EditWarDetector.is_article_in_edit_war(article, info.start_date, interval, False)
                    info.edit_war_over_time_list.insert(i, edit_war_value)

                xvals.append(interval.strftime("%d/%m/%y"))
                yvals.append(int(edit_war_value))

                clear_n_lines(1)
                print(f'\t\tIntervals with edit war value calculated {i+1}/{len(intervals)}')

            clear_n_lines(3)

        print("\n")

        # Set graph's configuration
        size = os.get_terminal_size()
        width = size.columns
        height = size.lines
        plt.plot_size(width=width, height=height)

        yticks = [0]
        for i in range(0, 10):
            yticks.append(round(yvals[-1] - (yvals[-1] / 10) * i))
        plt.yticks(yticks)

        plt.canvas_color("black")
        plt.axes_color("black")
        plt.ticks_color("white")
        plt.title("CONFLICT'S TEMPORAL EVOLUTION")
        plt.xlabel("TIME")
        plt.ylabel('EDIT WAR VALUES')
        plt.bar(xvals, yvals, color="blue")

        plt.show()


    def print_fighting_editors(self, info) -> dict[str, int]:
        fighting_editors_dict: dict[str, int] = {}
        for mutual_reverts_tuple in info.mutual_reverts_list:
            user_i = mutual_reverts_tuple[0][0].get("user")
            user_j = mutual_reverts_tuple[0][1].get("user")
            fighting_editors_dict[user_i] = fighting_editors_dict.get(user_i, 1) + 1
            fighting_editors_dict[user_j] = fighting_editors_dict.get(user_j, 1) + 1

        # Order resulting dict
        fighting_editors_dict = dict(sorted(fighting_editors_dict.items(), key=lambda item: item[1], reverse=True))

        print("\n\t- Fighting editors ordered from higher to lower activity (based on the nº of mutual reverts "
              "made): ")
        print("\n\t\tRANK --> EDITOR --> Nº OF MUTUAL REVERTS")
        for i, (user_i, edits) in enumerate(fighting_editors_dict.items()):
            print(f'\t\t{i + 1} --> {user_i} --> {edits}')

        return fighting_editors_dict


    def print_most_reverted_revisions(self, info):
        reverted_revisions_dict = {}
        for rev_i, rev_j, reverted_users in info.reverts_list:
            if rev_i['revid'] not in reverted_revisions_dict:
                reverted_revisions_dict[rev_i['revid']] = [rev_i, [rev_j]]
            else:
                reverted_revisions_dict[rev_i['revid']][1].append(rev_j)

        # Extract top 10 most reverted revisions
        top10 = heapq.nlargest(10, reverted_revisions_dict.items(), key=lambda item: len(item[1][1]))

        print(f'\n\t- Top {len(top10)} most reverted revisions, along with the number of reverts (a high number may '
              f'indicate bots\' presence, trying to impose the narrative of a particular revision): ')
        print("\n\t\tRANK --> [REVISION ID, TIMESTAMP, AUTHOR] --> Nº OF REVERTS TO THAT REVISION")
        for i, (rev_id, [rev, reverts_list]) in enumerate(top10):
            print(f'\t\t{i+1} --> [{rev_id}, {rev['timestamp']}, {rev.get('user', 'No user info available')}] '
                  f'--> {len(reverts_list)}')

        return reverted_revisions_dict


    @classmethod
    def __inspect_user_menu(cls, ordered_fighting_editors_dict):
        user_name = input("Please indicate the name of the user you want to inspect ")

        while ordered_fighting_editors_dict.get(user_name) is None:
            user_name = input("Name not found on the list, please try again ")

        user = User(WikiCrawler.site, user_name)

        clear_terminal()
        print(cls.MENU_DELIMITER)
        print(f'Selected user: {user.username}')
        print(cls.RESULTS_DELIMITER)
        print("User info:")
        print(f'\n\t- Username: {user.username} \n\n\t- Is registered?: {user.isRegistered()} '
              f'\n\n\t- Is blocked?: {user.is_blocked()} \n\n\t- Registration date: {user.registration()} '
              f'\n\n\t- Nº of global user edits (0 for anonymous users, ie. IP) {user.editCount()}')

        ipv4_pattern = r'^((25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.|$)){4}$'
        ipv6_pattern = r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'
        if re.fullmatch(ipv4_pattern, user.username) or re.fullmatch(ipv6_pattern, user.username):
            whois = IPWhois(user.username)
            result = whois.lookup_rdap()

            print(f'\n\t- ASN: {result["asn"]} ({result["asn_description"]})')
            network = result.get("network", {})
            print(f'\n\t- Network: {network.get("handle")} ({network.get("name")}) '
                  f'\n\n\t- Country: {network.get("country")}')

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
                    print(tabbed_info)

        input(cls.CONTINUE_MSG)

    @classmethod
    def __inspect_revision_menu(cls, info, reverted_revisions_dict):
        rev_id = input("Please indicate the ID of the revision you want to inspect ")

        selected_rev = None
        while selected_rev is None:
            for r in info.history_list:
                if str(r['revid']) == rev_id:
                    selected_rev = r
                    break
            if selected_rev is None:
                input("ID not found on article's history page, please try a different one ")

        clear_terminal()
        print(cls.MENU_DELIMITER)
        print(f'Selected revision: {selected_rev['revid']}')
        print(cls.RESULTS_DELIMITER)
        print("Revision info:")
        print(f'\n\t- ID: {selected_rev['revid']} \n\n\t- Timestamp: {selected_rev['timestamp']} '
              f'\n\n\t- Author: {selected_rev.get('user', 'No user info available')} '
              f'\n\n\t- Comment: {selected_rev.get('comment', 'No comment included')}')

        print("\n\t- List of reverts made to this revision: ")
        reverts_list = reverted_revisions_dict[int(rev_id)][1]
        print("\n\t\tREV ID, TIMESTAMP, USER")
        for rev in reverts_list:
            print(f'\n\t\t{rev['revid']}, {rev['timestamp']}, {rev.get('user', 'No user info available')}')

        rev_date = datetime.strptime(selected_rev['timestamp'], "%Y-%m-%dT%H:%M:%SZ")
        contents = WikiCrawler.get_full_revisions_in_range(info.article, rev_date, rev_date,
                                                           include_text = True)[0]['slots']['main']['*']
        print(f'\n\t- Contents: \n\n{contents}')

        input(cls.CONTINUE_MSG)

    def searched_articles_menu(self) -> int:
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
                WikiCrawler.print_pages(self.articles_set)
                print("\nArticles added: " + str(len(self.articles_set)) + "\n")
                _shared_dict["lines_to_remove"] = _shared_dict.get("lines_to_remove", 0) + len(self.articles_set) + 4

        # Show options
            idx = validate_idx(input("Select index of the article you want to add to search set (0 to return) "),
                                     0, len(self.search_articles_set))
            _shared_dict["lines_to_remove"] = _shared_dict.get("lines_to_remove", 0) + 1

            if idx != '0':
                self.articles_set.add(self.search_articles_set[int(idx)-1])
                clear_n_lines(_shared_dict.get("lines_to_remove", 0))
            else:
                self.search_articles_set.clear()

            _shared_dict["lines_to_remove"] = 0

        return idx


    def searched_categories_menu(self):
        clear_terminal()
        print(self.MENU_DELIMITER)

        # Show search results
        WikiCrawler.print_pages(self.search_categories_set)
        print(f'\nResults found: {len(self.search_categories_set)}\n')

        # Show options
        idx = ""
        while idx != '0':
            idx = validate_idx(input("Select index of the category for which you want to search related articles (0 to return) "),
                           0, len(self.search_categories_set))

            if idx != '0':
                limit = input("How many pages do you want to search at most? (Enter for no limit) ")

                while limit != "" and (not limit.isdigit() or int(limit) <= 0):
                    limit = input("Invalid limit, introduce a value higher than zero ")

                limit = None if limit == "" else int(limit)

                pages = WikiCrawler.crawl_articles((self.search_categories_set[int(idx)]).title(), search_limit=limit, search_type=1)

                for page in pages:
                    self.search_articles_set.add(page)

                if len(self.search_articles_set) == 0:
                    input("Search yielded no results try another category (Enter to continue) ")
                else:
                    idx_2 = ""
                    while idx_2 != '0':
                        idx_2 = self.searched_articles_menu()

                    # Print menu contents again
                    clear_terminal()
                    print(self.MENU_DELIMITER)
                    WikiCrawler.print_pages(self.search_categories_set)
                    print(f'\nResults found: {len(self.search_categories_set)}\n')
            else:
                self.search_categories_set.clear()

        return idx


    def delete_articles_menu(self):
        clear_terminal()
        print(self.MENU_DELIMITER)

        # Show articles in set
        WikiCrawler.print_pages(self.articles_set)
        print(f'\nArticles in search set: {len(self.articles_set)}\n')

        # Show options
        idx = validate_idx(input("Select index of the article you want to delete from search set (0 to return) "),
                           0, len(self.articles_set))
        if idx != '0':
            # If edit war analysis option has not been used yet
            if len(_articles_with_edit_war_info_dict) != 0:
                _articles_with_edit_war_info_dict.pop(self.articles_set[int(idx)-1])

            self.articles_set.pop(int(idx)-1)

        return idx



