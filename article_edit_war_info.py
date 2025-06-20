import pywikibot
from datetime import datetime, timedelta

from wiki_crawler import WikiCrawler

class ArticleEditWarInfo(object):
    _article: pywikibot.Page                 # Referenced article
    _start_date: datetime                    # Date from which the article is starting to be analyzed
    _end_date: datetime                      # Date from which the article stops to be analyzed
    _is_in_edit_war: bool                    # Tag indicating if there is an edit war in the article
    _edit_war_over_time_list: list[int]      # List with edit war values splitting the timeline on equal-length intervals

    # List with all the reverts on the article for the specified # timeline
    _reverts_list: list[tuple[pywikibot.page._revision, pywikibot.page._revision, set[str]]]

    # List with pairs of mutual reverts (user A reverts user B and B reverts A)
    _mutual_reverts_list: list[tuple[tuple[pywikibot.page._revision, pywikibot.page._revision, set[str]],
                         tuple[pywikibot.page._revision, pywikibot.page._revision, set[str]]]]

    _mutual_reversers_dict: dict[str, int]   # Dictionary with the nº of edits for each mutual reverser
    _history_list: list[pywikibot.page]      # History page (list of revisions)
    _discussion_page: pywikibot.page         # Discussion page #article.toggleTalkPage()


    def __init__(self, article, start_date, end_date, is_in_edit_war = None, edit_war_value = None, reverts_list = None, mutual_reverts_list = None, mutual_reversers_dict = None):
        self._article = article
        self._start_date = start_date
        self._end_date = end_date
        self._is_in_edit_war = is_in_edit_war
        self._edit_war_over_time_list = [edit_war_value] if edit_war_value is not None else None
        self.reverts_list = reverts_list if reverts_list is not None else []
        self.mutual_reverts_list = mutual_reverts_list if mutual_reverts_list is not None else []
        self.mutual_reversers_dict = mutual_reversers_dict if mutual_reversers_dict is not None else {}
        self._history_list= WikiCrawler.revisions_within_range(article, start_date, end_date)
        self._discussion_page = article.toggleTalkPage()


    @property
    def article(self):
        return self._article

    @property
    def start_date(self):
        return self._start_date

    @property
    def end_date(self):
        return self._end_date

    @property
    def is_in_edit_war(self):
        return self._is_in_edit_war

    @property
    def edit_war_over_time_list(self):
        return self._edit_war_over_time_list

    @property
    def reverts_list(self):
        return self._reverts_list

    @property
    def mutual_reverts_list(self):
        return self._mutual_reverts_list

    @property
    def mutual_reversers_dict(self):
        return self._mutual_reversers_dict

    @property
    def history_list(self):
        return self._history_list

    @property
    def discussion_page(self):
        return self._discussion_page

    @is_in_edit_war.setter
    def is_in_edit_war(self, value):
        self._is_in_edit_war = value

    @edit_war_over_time_list.setter
    def edit_war_over_time_list(self, value):
        self._edit_war_over_time_list = value

    @reverts_list.setter
    def reverts_list(self, value):
        self._reverts_list = value

    @mutual_reverts_list.setter
    def mutual_reverts_list(self, value):
        self._mutual_reverts_list = value

    @mutual_reversers_dict.setter
    def mutual_reversers_dict(self, value):
        self._mutual_reversers_dict = value


    @staticmethod
    def split_time_interval(start_date: datetime, end_date: datetime, n_intervals: int = 10) -> list[datetime]:
        intervals = []

        if end_date < start_date:
            start_date, end_date = end_date, start_date

        total_days = (end_date - start_date).days

        if total_days <= 10:
            for i in range(total_days):
                intervals.append(start_date + timedelta(days=i))
        else:
            interval_length = (end_date - start_date).days / 10
            for i in range(1, n_intervals + 1):
                intervals.append(start_date + timedelta(days=i * interval_length))

        return intervals