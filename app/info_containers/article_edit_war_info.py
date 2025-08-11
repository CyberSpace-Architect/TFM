from datetime import datetime, timedelta

from app.info_containers.local_page import LocalPage
from app.info_containers.local_revision import LocalRevision


class ArticleEditWarInfo(object):
    _article: LocalPage                      # Referenced article
    _start_date: datetime                    # Date from which the article is starting to be analyzed
    _end_date: datetime                      # Date from which the article stops to be analyzed

    # List with edit war values splitting the time range on equal-length intervals
    _edit_war_over_time_list: list[(int, datetime)]

    # History page (list with all the revisions for the specified time range)
    _revs_list: list[LocalRevision]

    # List with all the reverts on the article for the specified time range
    _reverts_list: list[tuple[LocalRevision, LocalRevision, set[str]]]

    # List with pairs of mutual reverts (user A reverts user B and B reverts A)
    _mutual_reverts_list: list[tuple[tuple[LocalRevision, LocalRevision, set[str]],
                         tuple[LocalRevision, LocalRevision, set[str]]]]

    # Dictionary with the nº of mutual reverts made by each mutual reverter on this article and period
    _mutual_reverters_dict: dict[str, int]


    def __init__(self, article, start_date:datetime, end_date:datetime, edit_war_value:int = None, reverts_list = None,
                 mutual_reverts_list = None, mutual_reverters_dict = None):
        self._article = article
        self._start_date = start_date
        self._end_date = end_date
        self._edit_war_over_time_list = [(edit_war_value, end_date)] if edit_war_value is not None else []
        self._revs_list = []
        self._reverts_list = reverts_list if reverts_list is not None else []
        self._mutual_reverts_list = mutual_reverts_list if mutual_reverts_list is not None else []
        self._mutual_reverters_dict = mutual_reverters_dict if mutual_reverters_dict is not None else {}


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
    def edit_war_over_time_list(self):
        return self._edit_war_over_time_list

    @property
    def revs_list(self):
        return self._revs_list

    @property
    def reverts_list(self):
        return self._reverts_list

    @property
    def mutual_reverts_list(self):
        return self._mutual_reverts_list

    @property
    def mutual_reverters_dict(self):
        return self._mutual_reverters_dict

    @start_date.setter
    def start_date(self, value):
        self._start_date = value

    @end_date.setter
    def end_date(self, value):
        self._end_date = value

    @edit_war_over_time_list.setter
    def edit_war_over_time_list(self, value):
        self._edit_war_over_time_list = value

    @revs_list.setter
    def revs_list(self, value):
        self._revs_list = value

    @reverts_list.setter
    def reverts_list(self, value):
        self._reverts_list = value

    @mutual_reverts_list.setter
    def mutual_reverts_list(self, value):
        self._mutual_reverts_list = value

    @mutual_reverters_dict.setter
    def mutual_reverters_dict(self, value):
        self._mutual_reverters_dict = value


    def is_in_edit_war(self, edit_war_threshold: int) -> bool:
        """
        Function that works as a tag indicating if there is an edit war in the article

        :param edit_war_threshold:
        :return: bool
        """
        is_in_edit_war = False

        if self._edit_war_over_time_list[-1][0] > edit_war_threshold:
            is_in_edit_war = True

        return is_in_edit_war


    @staticmethod
    def split_time_interval(start_date: datetime, end_date: datetime, n_intervals: int = 10) -> list[datetime]:
        """
        Function that splits the time defined within start and end dates into n intervals (10 by default, or less
        than 10 if there are less than 10 days of difference between start and end dates)

        :param start_date:
        :param end_date:
        :param n_intervals:
        :return: list[datetime]
        """
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