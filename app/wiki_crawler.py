import math
import pywikibot

from datetime import datetime, timedelta
from sortedcontainers import SortedSet
from os import get_terminal_size
from urllib.parse import quote

from app.info_containers.local_page import LocalPage
from app.info_containers.local_revision import LocalRevision
from app.utils.helpers import datetime_to_iso, clear_n_lines
from app.utils.common import Singleton


class WikiCrawler(object):
    language_code = 'en'
    site = pywikibot.Site('en', 'wikipedia')


    @classmethod
    def set_language_code(cls, language_code):
        cls.language_code = language_code
        cls.site = pywikibot.Site(language_code, 'wikipedia')


    @classmethod
    def crawl_articles(cls, search, search_limit, search_type):
        match search_type:
            case 1:  # Search articles by category
                pages = pywikibot.Category(cls.site, search).articles(total=search_limit)
            case _:  # Search articles by title
                pages = cls.site.search(search, total=search_limit, namespaces=0)

        return pages


    @classmethod
    def print_pages(cls, local_pages: SortedSet[LocalPage], time_range: tuple[datetime, datetime] = None,
                    history_changes: bool = False, discussion_changes: bool = False, will_remove_lines: bool = False) \
                    -> bool:
        new_data_to_save = False

        # If history of discussion page contents will be displayed, time range is needed (provided or default)
        if history_changes or discussion_changes:
            if time_range is not None:
                start_date, end_date = time_range
            else:
                # Default values, start_date=30 days ago and end_date=Today
                start_date = datetime.now().replace(microsecond=0) - timedelta(days=30)
                end_date = datetime.now().replace(microsecond=0)

        # Print pages
        print("[ID] PAGE TITLE --> URL")
        idx = 0
        for local_page in local_pages:
            idx += 1

            # If not history nor discussion pages will be displayed, page contents are directly printed
            if not history_changes and not discussion_changes:
                # Print line with info
                info_line = f'[{idx}] {local_page.title} --> {local_page.full_url()}'
                print(info_line)

                # If printed lines will be removed later, they must be counted and this value saved
                if will_remove_lines:
                    terminal_width = get_terminal_size().columns
                    n_lines_printed = math.ceil(len(info_line) / terminal_width)
                    shared_dict = Singleton().shared_dict
                    shared_dict["lines_to_remove"] = shared_dict.get("lines_to_remove", 0) + n_lines_printed

            if history_changes:
                # Build history url
                title_encoded = quote(local_page.title.replace(" ", "_"))
                history_url = f"https://{cls.language_code}.wikipedia.org/w/index.php?title={title_encoded}&action=history"

                # Print line with info
                print(f'{local_page.title} --> {history_url}')

                info_dict = Singleton().articles_with_edit_war_info_dict

                # History revisions page changes within time range
                # If info is stored it is directly accessed
                if local_page in info_dict and info_dict[local_page].revs_list is not None:
                    history_page_revs = info_dict[local_page].revs_list

                else: # Otherwise it is requested to Wikipedia
                    print("\tRequesting history page contents to Wikipedia...")
                    history_page_revs = cls.get_full_revisions_in_range(cls.site, local_page.page, start_date, end_date)
                    clear_n_lines(1)

                    # Indicate that new data should be saved in database
                    new_data_to_save = True

                print(f'\tHistory page changes from {start_date.strftime("%d/%m/%Y %H:%M:%S")} to '
                      f'{end_date.strftime("%d/%m/%Y %H:%M:%S")}: {len(history_page_revs)}')

                cls.print_revs(history_page_revs)

            if discussion_changes:
                # Discussion page changes within time range
                # If info is stored it is directly accessed
                if (local_page.discussion_page_title is not None and local_page.discussion_page_url is not None
                        and local_page.discussion_page_text is not None):
                    print(f'{local_page.discussion_page_title} --> {local_page.discussion_page_url}')
                    print("\n" + local_page.discussion_page_text)

                else: # Otherwise it is requested to Wikipedia
                    discussion_page = local_page.page.toggleTalkPage()
                    local_page.discussion_page_title = discussion_page.title()
                    local_page.discussion_page_url = discussion_page.full_url()
                    local_page.discussion_page_text = discussion_page.text

                    print(f'{discussion_page.title()} --> {discussion_page.full_url()}')
                    print("\n" + discussion_page.text)

                    # Indicate that new data should be saved in database
                    new_data_to_save = True

        return new_data_to_save


    @classmethod
    def get_full_revisions_in_range(cls, site: pywikibot.site, article: pywikibot.Page, start: datetime, end: datetime,
                                    include_text: bool = False) -> list[LocalRevision]:
        # Make sure both datetimes are in UTC and with the right format
        start_str = datetime_to_iso(start)
        end_str = datetime_to_iso(end)

        # Ensure rvstart goes before rvend
        if start > end:
            start_str, end_str = end_str, start_str

        # Set request params
        local_revs_list = []
        rvcontinue = None

        while True:
            params = {
                "action": "query",
                "prop": "revisions",
                "titles": article.title(),
                "rvstart": start_str,
                "rvend": end_str,
                "rvdir": "newer",
                "rvlimit": "max",
                "rvslots": "main",
                "rvprop": "ids|timestamp|user|comment|sha1|size|tags",
                "format": "json"
            }
            if rvcontinue: # If contents were too large for a unique msg and further info must be collected
                params["rvcontinue"] = rvcontinue
            if include_text: # If revision text wants to be retrieved too
                params["rvprop"] += "|content"

            # Create and send request
            request = site._request(**params)
            data = request.submit()

            # Extract request data
            page_id = next(iter(data["query"]["pages"]))
            for rev in data["query"]["pages"][page_id].get("revisions", []):
                local_revs_list.append(LocalRevision.init_with_revision(rev))

            # If there is still data that must be retrieved
            if "continue" in data:
                rvcontinue = data["continue"]["rvcontinue"]
            else: # Otherwise exit since all info has been extracted
                break

        return local_revs_list


    @staticmethod
    def print_revs(local_revs_array):
        print("\nREV ID, TIMESTAMP, USER, SIZE CHANGE, COMMENT")

        prev_size = 0
        for local_rev in local_revs_array:
            size_change = local_rev.size - prev_size
            prev_size = local_rev.size
            size_change = f'+{size_change}' if size_change > 0 else f'{size_change}'
            print(f'{local_rev.revid}, {local_rev.timestamp}, {local_rev.user}, {size_change}, "{local_rev.comment,}"')