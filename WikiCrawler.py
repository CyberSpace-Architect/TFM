import pywikibot
from datetime import datetime, timedelta
from sortedcontainers import SortedSet

import Utils
from EditWarDetector import EditWarDetector
#from EditWarDetectorTexto import EditWarDetector
#from EditWarDetectorPPdeep import EditWarDetector
from Utils import validate_idx, validate_date_format, clear_terminal, clear_n_lines

import logging
logging.getLogger("pywikibot.api").setLevel(logging.ERROR)


class WikiCrawler(object):
    CHOOSE_OPTION_MSG = "Select an option "
    INVALID_OPTION_MSG = "Invalid option, please select one of the list. (Enter to continue) "
    EMPTY_SET_MSG = "Search set empty, please first search some articles with option 1. (Enter to continue) "
    MENU_DELIMITER = "\n#################################################################\n"
    RESULTS_DELIMITER = "\n-----------------------------------------------------------------\n"
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

        while opt != '6':
            clear_terminal()
            print(self.MENU_DELIMITER)
            print("[1] Search articles by keywords")
            print("[2] Search articles related to one of the articles within the set")
            print("[3] Analyse presence of edit wars in articles within the set")
            print("[4] Analyse an article of the set in-depth")
            print("[5] Remove article from the set")
            print("[6] Exit\n")

            opt = input(self.CHOOSE_OPTION_MSG)
            match opt:
                case '1':
                    # Ask user about search parameters
                    search = input("What do you want to search for? ")

                    while search == "":
                        search = input("Search field cannot be empty, please try again ")

                    limit = input("How many pages do you want to search at most? (Enter for no limit) ")

                    while limit != "" and (not limit.isdigit() or int(limit) <= 0):
                        limit = input("Invalid limit, introduce a value higher than zero ")

                    limit = None if limit == "" else int(limit)

                    # Crawl wikipedia for articles
                    pages = self.crawl_articles(search, search_limit=limit, search_type=0)

                    # Save results in SortedSet as PageGenerator only allows to iterate it once
                    for page in pages:
                        self.search_articles_set.add(page)

                    if len(self.search_articles_set) == 0:
                        input("Search yielded no results (Enter to continue) ")
                        continue

                    # New menu until user wants to return
                    while opt != '0':
                        opt = self.searched_articles_menu()

                case '2':
                    # Check articles set has at least 1 article to search related categories
                    if len(self.articles_set) == 0:
                        #input(self.EMPTY_SET_MSG)
                        input(self.EMPTY_SET_MSG)
                        continue

                    # Show search set
                    self.print_pages(self.articles_set, time_range=None, history_changes=False, discussion_changes=False)
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
                    opt = ""
                    while opt != '0':
                        opt = self.searched_categories_menu()

                case '3':
                    # Check articles set is not empty before calculating edit-war values
                    if len(self.articles_set) == 0:
                        input(self.EMPTY_SET_MSG)
                        continue

                    start_date = input("Specify start date (dd/mm/YYYY) to count revisions of searched articles "
                                       "(leave blank and press Enter to use past 30 days) ")
                    if start_date == "":
                        start_date = (datetime.now() - timedelta(days=30))
                    else:
                        while not validate_date_format(start_date, self.DATE_FORMAT):
                            start_date = input("Invalid date, please, introduce a valid one ")
                        start_date = datetime.strptime(start_date, self.DATE_FORMAT)

                    end_date = input("Specify end date (dd/mm/YYYY) to count revisions of searched articles"
                                     " (leave blank and press Enter to use current date)")
                    if end_date == "":
                        end_date = datetime.now()
                    else:
                        while not validate_date_format(end_date, self.DATE_FORMAT):
                            end_date = input("Invalid date, please, introduce a valid one ")
                        end_date = datetime.strptime(end_date, self.DATE_FORMAT)

                    edit_war_detector = EditWarDetector(self.articles_set, start_date, end_date)
                    edit_war_detector.detect_edit_wars_in_set()

                    print(self.RESULTS_DELIMITER)
                    print("Summary of results:\n")
                    edit_war_detector.print_pages_with_tags()

                    input("\nEnter to return to Main menu ")

                case '4':
                    if len(self.articles_set) == 0:
                        input(self.EMPTY_SET_MSG)
                        continue

                case '5':
                    # Check articles set has at least 1 article to delete
                    if len(self.articles_set) == 0:
                        input(self.EMPTY_SET_MSG)
                        continue

                    while opt != '0':
                        opt = self.delete_articles_menu()

                # Exit
                case '6':
                    self.articles_set.clear()

                case _:
                    input(self.INVALID_OPTION_MSG)


    def searched_articles_menu(self):
        clear_terminal()
        print(self.MENU_DELIMITER)

        # Show search results
        self.print_pages(self.search_articles_set, time_range=None, history_changes=False, discussion_changes=False)
        print(f'\nResults found: {len(self.search_articles_set)}')

        print(self.RESULTS_DELIMITER)
        idx = ""

        while idx != '0':
            if len(self.articles_set) == 0:
                print("No articles added yet\n")
                Utils.shared_dict["lines_to_remove"] = Utils.shared_dict.get("lines_to_remove", 0) + 2
            else:
                self.print_pages(self.articles_set, time_range=None, history_changes=False, discussion_changes=False)
                print("\nArticles added: " + str(len(self.articles_set)) + "\n")
                Utils.shared_dict["lines_to_remove"] = Utils.shared_dict.get("lines_to_remove", 0) + len(self.articles_set) + 4

        # Show options
            idx = validate_idx(input("Select index of the article you want to add to search set (0 to return) "),
                                     0, len(self.search_articles_set))
            Utils.shared_dict["lines_to_remove"] = Utils.shared_dict.get("lines_to_remove", 0) + 1

            if idx != '0':
                self.articles_set.add(self.search_articles_set[int(idx) - 1])
                clear_n_lines(Utils.shared_dict.get("lines_to_remove", 0))
            else:
                self.search_articles_set.clear()

            Utils.shared_dict["lines_to_remove"] = 0

        return idx



    def searched_categories_menu(self):
        clear_terminal()
        print(self.MENU_DELIMITER)

        # Show search results
        self.print_pages(self.search_categories_set, time_range=None, history_changes=False, discussion_changes=False)
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

                pages = self.crawl_articles((self.search_categories_set[int(idx)]).title(), search_limit=limit, search_type=1)

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
                    self.print_pages(self.search_categories_set, time_range=None, history_changes=False,
                                     discussion_changes=False)
                    print(f'\nResults found: {len(self.search_categories_set)}\n')
            else:
                self.search_categories_set.clear()

        return idx


    def delete_articles_menu(self):
        clear_terminal()
        print(self.MENU_DELIMITER)

        # Show articles in set
        self.print_pages(self.articles_set, time_range=None, history_changes=False, discussion_changes=False)
        print(f'\nArticles in search set: {len(self.articles_set)}\n')

        # Show options
        idx = validate_idx(input("Select index of the article you want to delete from search set (0 to return) "),
                           0, len(self.articles_set))
        if idx != '0':
            self.articles_set.pop(int(idx) - 1)

        return idx


    def crawl_articles(self, search, search_limit, search_type):
        site = pywikibot.Site('es', 'wikipedia')

        match search_type:
            case 1:     # Search articles by category Categoría:Eventos políticos en curso
                pages = pywikibot.Category(site, search).articles(total=search_limit)
            case _:     # Search articles by title
                pages = site.search(search, total=search_limit, namespaces=0)

        return pages


    def print_pages(self, pages, time_range, history_changes: bool, discussion_changes: bool):
        if history_changes or discussion_changes:
            if time_range is not None:
                start_date, end_date = time_range
            else:
                start_date = datetime.now().replace(microsecond=0) - timedelta(days=30)
                end_date = datetime.now().replace(microsecond=0)

        print("[ID] PAGE TITLE --> URL")
        idx = 0

        for page in pages:
            idx += 1
            print(f'[{idx}] {page.title()} --> {page.full_url()}')

            if history_changes:
                # Discussion page changes within time range
                discussion_page = page.toggleTalkPage()
                discussion_page_revs = self.revisions_within_range(discussion_page, start_date, end_date)
                print(f'\n\tDiscussion page changes (from {start_date} to {end_date}): {len(discussion_page_revs)}')
                self.print_revs(discussion_page_revs)

            if discussion_changes:
                # History revisions page changes within time range
                history_page_revs = self.revisions_within_range(page, start_date, end_date)
                print(f'\tHistory page changes (from {start_date} to {end_date}): {len(history_page_revs)}')
                self.print_revs(history_page_revs)


    @staticmethod
    def revisions_within_range(page, start_date, end_date):
        result_revs = []

        # Get history page and create iterator
        revs = page.revisions(reverse=False, total=None)

        it = iter(revs)
        rev = next(it, None)

        if rev is not None:
            rev_date = rev.timestamp

            while rev is not None and rev_date > end_date:
                rev = next(it, None)
                if rev is not None:
                    rev_date = rev.timestamp

            if rev is not None:
                while rev is not None and rev_date > start_date:
                    result_revs.append(rev)

                    rev = next(it, None)
                    if rev is not None:
                        rev_date = rev.timestamp

        return result_revs



    def print_revs(self, rev_array):
        print("\n\t\tREV ID, TIMESTAMP, USER")
        for rev in rev_array:
            print(f'\t\t{rev.revid}, {rev.timestamp}, {rev.user}')
        print("")



