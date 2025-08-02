import urllib
import shutil
import math
import pywikibot

from datetime import datetime, timedelta
from sortedcontainers import SortedSet

from local_page import LocalPage
from local_revision import LocalRevision
from utils import datetime_to_iso, clear_n_lines, _shared_dict, _articles_with_edit_war_info_dict


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
    def print_pages(cls, local_pages: SortedSet[LocalPage], time_range: tuple[datetime, datetime] = None, history_changes: bool = False,
                    discussion_changes: bool = False, will_remove_lines: bool = False):
        if history_changes or discussion_changes:
            if time_range is not None:
                start_date, end_date = time_range
            else:
                start_date = datetime.now().replace(microsecond=0) - timedelta(days=30)
                end_date = datetime.now().replace(microsecond=0)

        print("[ID] PAGE TITLE --> URL")
        idx = 0

        for local_page in local_pages:
            idx += 1

            if not history_changes and not discussion_changes:
                terminal_width = shutil.get_terminal_size().columns
                msg = f'[{idx}] {local_page.title} --> {local_page.full_url()}'
                print(msg)
                if will_remove_lines:
                    n_lines_printed = math.ceil(len(msg) / terminal_width)
                    _shared_dict["lines_to_remove"] = _shared_dict.get("lines_to_remove", 0) + n_lines_printed

            if history_changes:
                # Build history url
                title_encoded = urllib.parse.quote(local_page.title.replace(" ", "_"))
                history_url = f"https://{cls.language_code}.wikipedia.org/w/index.php?title={title_encoded}&action=history"
                print(f'{local_page.title} --> {history_url}')

                # History revisions page changes within time range
                if local_page in _articles_with_edit_war_info_dict and \
                    _articles_with_edit_war_info_dict[local_page].revs_list is not None:
                        history_page_revs = _articles_with_edit_war_info_dict[local_page].revs_list
                else:
                    print("\tRequesting history page contents to Wikipedia...")
                    history_page_revs = cls.get_full_revisions_in_range(cls.site, local_page.page, start_date, end_date)
                    clear_n_lines(1)

                print(f'\tHistory page changes from {start_date.strftime("%d/%m/%Y %H:%M:%S")} to '
                      f'{end_date.strftime("%d/%m/%Y %H:%M:%S")}: {len(history_page_revs)}')

                cls.print_revs(history_page_revs)

            if discussion_changes:
                # Discussion page changes within time range
                if (local_page.discussion_page_title is not None and local_page.discussion_page_url is not None
                        and local_page.discussion_page_text is not None):
                    print(f'{local_page.discussion_page_title} --> {local_page.discussion_page_url}')
                    print("\n" + local_page.discussion_page_text)
                else:
                    discussion_page = local_page.page.toggleTalkPage()
                    local_page.discussion_page_title = discussion_page.title()
                    local_page.discussion_page_url = discussion_page.full_url()
                    local_page.discussion_page_text = discussion_page.text

                    print(f'{discussion_page.title()} --> {discussion_page.full_url()}')
                    print("\n" + discussion_page.text)


    @classmethod
    def get_full_revisions_in_range(cls, site: pywikibot.site, article: pywikibot.Page, start: datetime, end: datetime,
                                    include_text: bool = False) -> list[LocalRevision]:
        # Make sure both datetimes are in UTC and with right format
        start_str = datetime_to_iso(start)
        end_str = datetime_to_iso(end)

        # Ensure rvstart goes before rvend
        if start > end:
            start_str, end_str = end_str, start_str

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
            if rvcontinue:
                params["rvcontinue"] = rvcontinue
            if include_text:
                params["rvprop"] += "|content"

            request = site._request(**params)
            data = request.submit()

            page_id = next(iter(data["query"]["pages"]))

            for rev in data["query"]["pages"][page_id].get("revisions", []):
                local_revs_list.append(LocalRevision.init_with_revision(rev))

            if "continue" in data:
                rvcontinue = data["continue"]["rvcontinue"]
            else:
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