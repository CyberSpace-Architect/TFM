import heapq
import re
import pywikibot
import plotext as plt

from datetime import datetime, timedelta

from sortedcontainers import SortedSet
from babel import Locale, localedata

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

                    input("\nEnter to return to Main menu ")

                case '4':
                    # Check articles set has at least 1 article to inspect
                    if len(self.articles_set) == 0:
                        input(self.EMPTY_SET_MSG)
                        continue

                    # New menu until user wants to return
                    opt_2 = ""
                    while opt_2 != '0':
                        opt_2 = self.inspect_article_in_depth_menu()

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
                                                               f'to change it?').lower())

        while change_language not in {"y", "yes", "n", "no"}:
            change_language = re.sub(r'\s+', '', input("Invalid response, please write y or yes if you want"
                                                                   " to change it, n or no otherwise: ").lower())

        if change_language in {"y", "yes"}:
            language_codes = sorted(pywikibot.family.Family.load("wikipedia").langs.keys())

            idx = 0
            while idx < len(language_codes):
                code = language_codes[idx]
                if localedata.exists(code):
                    language = Locale(code).get_display_name('en')  # Name in English
                    print(f'[{idx+1}] {language}')
                    idx += 1
                else:
                    language_codes.pop(idx)

            idx = input("Select index of the language of the Wiki in which you want to search: ")
            idx = int(validate_idx(idx, 0, len(language_codes) - 1))

            WikiCrawler.set_language_code(language_codes[idx-1])
            language = Locale(language_codes[idx]).get_display_name('en')

        return search, limit, language


    def inspect_article_in_depth_menu(self):
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
            if _articles_with_edit_war_info_dict.get(article) is None:
                input('Please, select option 3 in main menu before requesting in-depth analysis of an article (Enter '
                      'to continue)')
                return '0'

            clear_terminal()
            print(self.MENU_DELIMITER)
            print(f'Selected article: {article.title()} ({article.full_url()})')

            print(self.RESULTS_DELIMITER)
            print("Article info:")
            info = _articles_with_edit_war_info_dict[article]

            # Conflict severity (edit war value for the whole time period)
            edit_war_value = info.edit_war_over_time_list[0]
            print(f'\n\t- Conflict severity (edit war value, higher than '
                  f'{EditWarDetector.EDIT_WAR_THRESHOLD} is considered edit war): {edit_war_value}')

            # Conflict's size (nº of users mutually reverting each other
            n_mutual_reversers = len(info.mutual_reversers_dict)
            print(f'\t- Conflict\'s size (nº of users mutually reverting each other): {n_mutual_reversers}')

            # Conflict's temporal evolution TO DO
            print("\t- Conflict's temporal evolution (graph with edit war values over time): ")
            print("\t==> Calculating edit war values to plot...\n")
            intervals = ArticleEditWarInfo.split_time_interval(info.start_date, info.end_date)
            xvals, yvals = [], []

            for i, interval in enumerate(intervals):
                _, edit_war_value = EditWarDetector.is_article_in_edit_war(article, info.start_date, interval, False)
                info.edit_war_over_time_list.append(edit_war_value)

                xvals.append(interval.strftime("%d/%m/%Y"))
                yvals.append(int(edit_war_value))

                clear_n_lines(1)
                print(f'\tIntervals with edit war value calculated {i+1}/{len(intervals)}')

            yticks = [0]
            for i in range(0, 10):
                yticks.append(round(yvals[-1] - (yvals[-1]/10) * i))
            plt.yticks(yticks)
            plt.canvas_color("black")
            plt.axes_color("black")
            plt.ticks_color("white")
            plt.title("CONFLICT'S TEMPORAL EVOLUTION")
            plt.xlabel("TIME")
            plt.ylabel('EDIT WAR VALUES')
            plt.bar(xvals, yvals)

            # 4) Mostrar el valor Y encima de cada barra
            #for x, y in zip(xvals, yvals):
            #    plt.text(str(y), x, y + max(yvals)*0.01, alignment="center")
            plt.show()

            # Fighting editors ordered from higher to lower activity (based on the nº of mutual reverts made)
            fighting_editors_dict: dict[str, int] = {}
            for mutual_reverts_tuple in info.mutual_reverts_list:
                user_i = mutual_reverts_tuple[0][0].get("user")
                user_j = mutual_reverts_tuple[0][1].get("user")
                fighting_editors_dict[user_i] = fighting_editors_dict.get(user_i, 1) + 1
                fighting_editors_dict[user_j] = fighting_editors_dict.get(user_j, 1) + 1
            # Order resulting dict
            fighting_editors_dict = dict(sorted(fighting_editors_dict.items(), key=lambda item: item[1], reverse=True))
            print("\n   \t- Fighting editors ordered from higher to lower activity (based on the nº of mutual reverts made): ")
            print("\n\t\tRANK --> EDITOR --> Nº OF MUTUAL REVERTS")
            for i, (user_i, edits) in enumerate(fighting_editors_dict.items()):
                print(f'\t\t{i+1} --> {user_i} --> {edits}')

            # Top 5 most reverted revisions, along with the number of reverts
            reverted_revisions_dict = {}
            for reverting_revision, reverted_revision, reverted_users in info.reverts_list:
                if not reverted_revisions_dict.__contains__(reverted_revision['revid']):
                    reverted_revisions_dict[reverted_revision['revid']] = [reverted_revision, 1]
                else:
                    reverted_revisions_dict[reverted_revision['revid']][1] += 1
            # Extract top 5 most reverted revisions
            top5 = heapq.nlargest(5, reverted_revisions_dict.values(), key=lambda item: item[1])
            print("\n\t- Top 5 most reverted revisions, along with the number of reverts (a high number may indicate"
                  " bots' presence, trying to impose the narrative of a particular revision): ")
            print("\n\t\tRANK --> [REVISION ID, EDITOR, TIMESTAMP] --> Nº OF REVERTS TO THAT REVISION")
            for i, (revision, n_reverts) in enumerate(top5):
                print(f'\t\t{i+1} --> [{revision['revid']}, {revision['user']}, {revision['timestamp']}] --> {n_reverts}')

            opt = ""
            while opt != '0':
                print(self.RESULTS_DELIMITER)
                print("[1] Inspect a user on the list")
                print("[2] Inspect a revision on the list")
                print("[0] Return to articles' list\n")

                opt = input(self.CHOOSE_OPTION_MSG)
                _shared_dict["lines_to_remove"] = _shared_dict.get("lines_to_remove", 0) + 9
                match opt:
                    case '1':
                        opt = self.inspect_user_menu()
                    case '2':
                        opt = self.inspect_revision_menu()
                    case '0':
                        continue
                    case _:
                        input(self.INVALID_OPTION_MSG)
                        clear_n_lines(_shared_dict.get("lines_to_remove", 0))
                        _shared_dict["lines_to_remove"] = 0

        return idx



    def searched_articles_menu(self):
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



