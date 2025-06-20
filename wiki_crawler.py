import pywikibot
from datetime import datetime, timedelta

from utils import datetime_to_iso



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
            case 1:  # Search articles by category Categoría:Eventos políticos en curso
                pages = pywikibot.Category(cls.site, search).articles(total=search_limit)
            case _:  # Search articles by title
                pages = cls.site.search(search, total=search_limit, namespaces=0)

        return pages


    @classmethod
    def print_pages(cls, pages, time_range: tuple[datetime, datetime] = None, history_changes: bool = False,
                    discussion_changes: bool = False):
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
                # History revisions page changes within time range
                history_page_revs = cls.revisions_within_range(page, start_date, end_date)
                print(f'\tHistory page changes (from {start_date} to {end_date}): {len(history_page_revs)}')
                cls.print_revs(history_page_revs)

            if discussion_changes:
                # Discussion page changes within time range
                discussion_page = page.toggleTalkPage()
                discussion_page_revs = cls.revisions_within_range(discussion_page, start_date, end_date)
                print(f'\n\tDiscussion page changes (from {start_date} to {end_date}): {len(discussion_page_revs)}')
                cls.print_revs(discussion_page_revs)


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


    @classmethod
    def get_full_revisions_in_range(cls, article: pywikibot.Page, start: datetime, end: datetime) -> list[pywikibot.Page]:
        # Make sure both datetimes are in UTC and with right format
        start_str = datetime_to_iso(start)
        end_str = datetime_to_iso(end)

        # Ensure rvstart goes before rvend
        if start > end:
            start_str, end_str = end_str, start_str

        revs_list = []
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
                "rvprop": "ids|timestamp|user|comment|sha1",
                "format": "json"
            }
            if rvcontinue:
                params["rvcontinue"] = rvcontinue

            request = cls.site._request(**params)
            data = request.submit()

            page_id = next(iter(data["query"]["pages"]))
            revs_list.extend(data["query"]["pages"][page_id].get("revisions", []))

            if "continue" in data:
                rvcontinue = data["continue"]["rvcontinue"]
            else:
                break

        return revs_list


    @staticmethod
    def print_revs(rev_array):
        print("\n\t\tREV ID, TIMESTAMP, USER")
        for rev in rev_array:
            print(f'\t\t{rev.revid}, {rev.timestamp}, {rev.user}')
        print("")