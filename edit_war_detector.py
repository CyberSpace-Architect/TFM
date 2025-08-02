import pywikibot
from datetime import datetime, timedelta
from typing import Any

from sortedcontainers import SortedSet

from local_revision import LocalRevision
from utils import clear_n_lines, _articles_with_edit_war_info_dict
from wiki_crawler import WikiCrawler
from article_edit_war_info import ArticleEditWarInfo
from local_page import LocalPage

class EditWarDetector(object):
    EDIT_WAR_THRESHOLD = 100

    @classmethod
    def detect_edit_wars_in_set(cls, articles_set: SortedSet[LocalPage], start_date: datetime, end_date: datetime):

        print("\n===> Starting detection of edit wars...")
        for local_page in articles_set:
            print(f"\nAnalyzing article {local_page.title}")
            info: ArticleEditWarInfo = _articles_with_edit_war_info_dict.get(local_page)

            if info is None or not info.revs_list:
                # No previous data for this article, so all revisions have to be retrieved from Wikipedia
                _articles_with_edit_war_info_dict[local_page] = ArticleEditWarInfo(local_page.page, start_date, end_date)
                info = _articles_with_edit_war_info_dict[local_page]

                # Get revisions from Wikipedia
                print("\tNo previous data stored for this article, requesting revisions to Wikipedia")
                info.revs_list = WikiCrawler.get_full_revisions_in_range(WikiCrawler.site, local_page.page, start_date, end_date)
                print(f"\t\tRevisions received, number of revisions within time range: {len(info.revs_list)}")
            else:
                cls.update_revisions_to_new_time_range(local_page, start_date, end_date)
                info: ArticleEditWarInfo = _articles_with_edit_war_info_dict[local_page]

            (info.reverts_list, info.mutual_reverts_list, info.mutual_reverters_dict,
                edit_war_value) = cls.is_article_in_edit_war(info.revs_list, True)

            info.edit_war_over_time_list = [(edit_war_value, end_date)]

    @classmethod
    def update_revisions_to_new_time_range(cls, local_page: LocalPage, start_date: datetime, end_date: datetime):

        # Check if the time range has changed and new revisions have to be retrieved from Wikipedia
        info: ArticleEditWarInfo = _articles_with_edit_war_info_dict[local_page]

        if abs(start_date - info.start_date) >= timedelta(days=1) or abs(end_date - info.end_date) >= timedelta(days=1):
            # Perform appropriate actions depending on the new time range compared to the old one
            print("\tPrevious data stored for this article, but time range has been changed (at least "
                  "\n\ta day of difference between start or end dates respect to previous ones),"
                  "\n\tadjusting revisions to new range... ")

            # Retrieve page from Wikipedia to be able to retrieve missing revisions
            if not local_page.page:
                fam, code = local_page.site.split(":", 1)
                site = pywikibot.Site(code, fam)
                local_page.page = next(site.load_pages_from_pageids([local_page.pageid]))

            n_revs_received = 0
            n_revs_deleted = 0

            if start_date < info.start_date:
                new_revs_list = WikiCrawler.get_full_revisions_in_range(WikiCrawler.site, local_page.page, start_date,
                                                                        info.start_date)
                n_revs_received += len(new_revs_list)
                info.revs_list[:0] = new_revs_list
            else:
                start_date_reached = False

                while not start_date_reached:
                    rev_date = info.revs_list[0].timestamp

                    if datetime.strptime(rev_date, "%Y-%m-%dT%H:%M:%SZ") > start_date:
                        start_date_reached = True
                    else:
                        info.revs_list.pop(0)
                        n_revs_deleted += 1
            if info.end_date < end_date:
                new_revs_list = WikiCrawler.get_full_revisions_in_range(WikiCrawler.site, local_page.page, info.end_date,
                                                                        end_date)
                n_revs_received += len(new_revs_list)
                info.revs_list.extend(new_revs_list)
            else:
                end_date_reached = False

                while not end_date_reached:
                    rev_date = info.revs_list[-1].timestamp

                    if datetime.strptime(rev_date, "%Y-%m-%dT%H:%M:%SZ") < end_date:
                        end_date_reached = True
                    else:
                        info.revs_list.pop(-1)
                        n_revs_deleted += 1

            print(f"\t\tNew revisions received from Wikipedia: {n_revs_received} ")
            print(f"\t\tNon-necessary revisions deleted: {n_revs_deleted} ")
            print(f"\t\tTotal number of revisions within new time range: {len(info.revs_list)}")

        else:
            print("\tPrevious data stored for this article and time range has not changed"
                  "\n\t(less than a day of difference between start and end dates compared to previous ones),"
                  "\n\tno missing revisions needed to be requested to Wikipedia")

        # Save new time range
        info.start_date = start_date
        info.end_date = end_date


    @classmethod
    def is_article_in_edit_war(cls, revs_list: list[LocalRevision], print_info: bool = False):
        edit_war_tag = False

        # Find and store all reverts
        reverts_list = cls._find_reverts(revs_list, print_info)

        # Filter reverts and keep only mutual ones
        mutual_reverts_list = cls._find_mutual_reverts(reverts_list, print_info)

        # Calculate Nr value (min of nº edits) of each pair of mutual reverters from mutual reverts list,
        # a dictionary with the nº of edits for each mutual reverters is retrieved too
        nr_values_list, mutual_reverters_dict = cls.__calculate_nr_values(mutual_reverts_list, revs_list)

        # Calculate E value as the total number of mutual reverters (length of mutual reverters' dict - 1 to skip max
        # value deleted from nr_values_list)
        n_mutual_reverters = len(mutual_reverters_dict) - 1

        # Calculate edit_war value as the sum of Nr values multiplied by the E value
        edit_war_value = cls.__calculate_edit_war_value(n_mutual_reverters, nr_values_list)

        # Alert of edit war in the article if the value surpasses the threshold
        if edit_war_value > cls.EDIT_WAR_THRESHOLD:
            edit_war_tag = True

        if print_info: print(f"Analysis finished, article with edit war (value > {cls.EDIT_WAR_THRESHOLD})?: {edit_war_tag} "
                             f"(edit war value: {edit_war_value})")

        return reverts_list, mutual_reverts_list, mutual_reverters_dict, edit_war_value


    @classmethod
    def _find_reverts(cls, revs_list: list[LocalRevision], print_info: bool) \
            -> list[tuple[LocalRevision, LocalRevision, set[str]]]:
        if print_info: print("\tStarting to analyse each revision within time range for reverts\n")

        reverted_users_set = set[str]()
        reverts_list: list[tuple[pywikibot.page._revision, pywikibot.page._revision, set[str]]] = []
        revs_with_revert_idxs_set = set[int]()

        # Traverse revisions list looking for reverts (skipping self-reverts) and store them when found
        for i in range(0, len(revs_list)-2):
            local_rev_i = revs_list[i]
            rev_i_user = local_rev_i.user

            # Skip this revision if it has already been counted in a previous revert or is part of anti-vandalism bots'
            # activity
            if i in revs_with_revert_idxs_set or cls.__is_known_bot(rev_i_user):
                continue

            # Add next rev user as possibly reverted user (next rev cannot cause a revert as it is necessary at least
            # an article in between to provoke one, otherwise, this and next revision would be identical)
            next_rev_user = revs_list[i+1].user
            if not cls.__is_known_bot(next_rev_user):
                reverted_users_set.add(next_rev_user)

            for j in range(i+2, len(revs_list)-1):
                local_rev_j = revs_list[j]
                rev_j_user = local_rev_j.user

                # Skip known antivandalism bots' activity
                if cls.__is_known_bot(rev_j_user):
                    continue

                if local_rev_i.sha1 == local_rev_j.sha1:
                    # (Exclude self reverts)
                    if rev_j_user in reverted_users_set:
                        reverted_users_set.remove(rev_j_user)

                    # Store the revert detected and the idx of the reverting revision to avoid analyzing it later
                    reverts_list.append((local_rev_i, local_rev_j, reverted_users_set.copy()))
                    revs_with_revert_idxs_set.add(j)
                    # The set is cleaned up since if a new revert is found later, the reverted users would be those
                    # between this last detected revert and the new one.
                    reverted_users_set.clear()

                # Rev_j is a revert to rev_i, so user from rev_j has commited a revert against all users of
                # revisions from i+1 to j-1, so we add all possibly reverted users to set
                reverted_users_set.add(rev_j_user)

            # Reset set after checking all possible reverts for revision i
            reverted_users_set.clear()

            if print_info:
                clear_n_lines(1)
                print(f"\t\tRevisions analyzed: {i+1}, total nº of reverts detected: {len(reverts_list)}")

        return reverts_list

    @staticmethod
    def __is_known_bot(user: str) -> bool:
        known_bots = {"serobot", "patrubot", "avbot", "avdiscubot", "botarel", "cvbot", "cvnbot"}
        is_known_bot = user.lower() in known_bots

        return is_known_bot

    @staticmethod
    def _find_mutual_reverts(reverts_list: list[tuple[LocalRevision, LocalRevision, set[str]]],
                             print_info: bool) -> list[tuple[tuple[LocalRevision, LocalRevision, set[str]],
                             tuple[LocalRevision, LocalRevision, set[str]]]]:
        if print_info:
            print("\tFiltering reverts keeping mutual ones\n")

        mutual_reverts_list: list[tuple[tuple[LocalRevision, LocalRevision, set[str]],
                             tuple[LocalRevision, LocalRevision, set[str]]]] = []

        # Traverse reverts list looking for mutual reverts and store them when found
        for i in range(len(reverts_list)):
            revert_1 = reverts_list[i]
            reverter_user = revert_1[1].user

            # For each user reverted, check if it has commited a revert against reverter_user (mutual revert)
            for reverted_user in revert_1[2]:
                for j in range(i + 1, len(reverts_list)):
                    revert_2 = reverts_list[j]

                    if reverted_user == revert_2[1].user and reverter_user in revert_2[2]:
                        mutual_reverts_list.append((revert_1, revert_2))

            if print_info:
                clear_n_lines(1)
                print(f"\t\tReverts analyzed: {i+1}, total nº of mutual reverts detected: {len(mutual_reverts_list)}")

        return mutual_reverts_list


    @classmethod
    def __calculate_nr_values(cls, mutual_reverts_list: list[tuple[tuple[LocalRevision, LocalRevision, set[str]],
                              tuple[LocalRevision, LocalRevision, set[str]]]], revs_list: list[LocalRevision]) \
                              -> tuple[list[int], dict[str, int]]:
        # Traverse mutual reverts list calculating the Nr value for each pair of mutual reverters
        # Nr value is calculated as the minimum of the total edits of each reverter. While doing so,
        # max Nr value is saved to remove this outlay from the set of Nr values
        max_nr = 0
        idx_max_nr = 0
        nr_values_list: list[int] = []
        mutual_reverters_dict: dict[str, int] = {}

        for mutual_reverts_tuple in mutual_reverts_list:
            user_i = mutual_reverts_tuple[0][1].user
            user_j = mutual_reverts_tuple[1][1].user

            # Count n_edits of user_i and user_j, if we have not stored already their edits number
            if mutual_reverters_dict.get(user_i) is None:
                mutual_reverters_dict[user_i] = cls._count_user_edits(user_i, revs_list)
            n_edits_i = mutual_reverters_dict[user_i]

            if mutual_reverters_dict.get(user_j) is None:
                mutual_reverters_dict[user_j] = cls._count_user_edits(user_j, revs_list)
            n_edits_j = mutual_reverters_dict[user_j]

            # Calculate Nr value for this mutual revert
            nr_value = min(n_edits_i, n_edits_j)
            nr_values_list.append(nr_value)

            # Update max Nr if necessary
            if max_nr < nr_value:
                max_nr = nr_value
                idx_max_nr = len(nr_values_list) - 1

        # Once finished drop max Nr value from list
        if len(nr_values_list) > 0:
            nr_values_list.pop(idx_max_nr)

        return nr_values_list, mutual_reverters_dict


    @staticmethod
    def _count_user_edits(user: Any, revs_list: list[LocalRevision]) -> int:
        n_edits = 0

        for local_rev in revs_list:
            if user == local_rev.user:
                n_edits += 1

        return n_edits


    @staticmethod
    def __calculate_edit_war_value(n_mutual_reverters: int, nr_values_list: list[int]) -> int:

        edit_war_value = 0

        for nr_value in nr_values_list:
            edit_war_value += nr_value

        edit_war_value = n_mutual_reverters * edit_war_value

        return edit_war_value


    @classmethod
    def print_pages_with_tags(cls, articles_with_edit_war_info_dict: dict[LocalPage, ArticleEditWarInfo]):
        print("[ID] PAGE TITLE --> URL --> EDIT_WAR")
        i = 0
        n_edit_wars = 0

        for i, (article, article_info) in enumerate(articles_with_edit_war_info_dict.items(), start=1):
            value = article_info.edit_war_over_time_list[-1][0]
            tag = value > cls.EDIT_WAR_THRESHOLD
            if tag:
                n_edit_wars += 1

            print(f'[{i}] {article.title} --> {article.full_url()} --> {tag} '
                  f'({value}/{cls.EDIT_WAR_THRESHOLD})')

        print(f'\nArticles analyzed: {i} \nArticles with edit war: {n_edit_wars}')