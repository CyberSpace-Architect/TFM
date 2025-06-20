import pywikibot
from datetime import datetime
from typing import Any
from sortedcontainers import SortedSet

from utils import clear_n_lines, _articles_with_edit_war_info_dict
from wiki_crawler import WikiCrawler
from article_edit_war_info import ArticleEditWarInfo

class EditWarDetector(object):
    EDIT_WAR_THRESHOLD = 100

    # Me he quedado en que reverts_list y mutual_reverts de esta clase tienen que estar asociados a cada
    # articulo si no se mezclan, reverts_list ya lo he modificado para el acceso a tupla, pero me parece
    # muy ofuscado (no se ve lo que representa cada valor de la tupla) por lo que estoy buscando una
    # forma de acceder usando los nombres reverts_list y mutual_reverts. Vale, tengo que cambiarlo para
    # que guarde ambas cosas en article_edit_war_info_dict

    @classmethod
    def detect_edit_wars_in_set(cls, articles_set: SortedSet[pywikibot.Page], start_date: datetime, end_date: datetime):
        # First, the set is cleared to avoid inconsistencies according to start and end dates from previous searches
        _articles_with_edit_war_info_dict.clear()

        print("\n===> Starting detection of edit wars...")

        for article in articles_set:
            print(f"\nAnalyzing article {article.title()}")

            _articles_with_edit_war_info_dict[article] = ArticleEditWarInfo(article, start_date, end_date)
            edit_war_tag, edit_war_value = cls.is_article_in_edit_war(article, start_date, end_date, True)

            _articles_with_edit_war_info_dict[article]._is_in_edit_war = edit_war_tag
            _articles_with_edit_war_info_dict[article].edit_war_over_time_list = [edit_war_value]


    @classmethod
    def is_article_in_edit_war(cls, article: pywikibot.Page, start_date: datetime, end_date: datetime, print_info: bool) -> [bool, int]:
        edit_war_tag = False

        if print_info: print("\tRequesting revisions to Wikipedia")
        revs_list = WikiCrawler.get_full_revisions_in_range(article, start_date, end_date)
        if print_info: print(f"\t\tRevisions received, number of revisions within time range: {len(revs_list)}")

        article_info = _articles_with_edit_war_info_dict[article]
        # Find and store all reverts
        article_info.reverts_list = cls._find_reverts(article, revs_list, print_info)

        # Filter reverts and keep only mutual ones
        article_info.mutual_reverts_list = cls._find_mutual_reverts(article, article_info.reverts_list, print_info)

        # Calculate Nr value (min of nº edits) of each pair of mutual reversers from mutual reverts list,
        # a dictionary with the nº of edits for each mutual reversers is retrieved too
        nr_values_list, article_info.mutual_reversers_dict = cls.__calculate_nr_values(article_info.mutual_reverts_list,
                                                                                       revs_list)

        # Calculate E value as the total number of mutual reversers (length of mutual reversers' dict)
        n_mutual_reversers = len(article_info.mutual_reversers_dict)

        # Calculate edit_war value as the sum of Nr values multiplied by the E value
        edit_war_value = cls.__calculate_edit_war_value(n_mutual_reversers, nr_values_list)

        # Alert of edit war in the article if the value surpasses the threshold
        if edit_war_value > cls.EDIT_WAR_THRESHOLD:
            edit_war_tag = True

        if print_info: print(f"Analysis finished, article with edit war (value > {cls.EDIT_WAR_THRESHOLD})?: {edit_war_tag} "
                             f"(edit war value: {edit_war_value})")

        return edit_war_tag, edit_war_value


    @classmethod
    def _find_reverts(cls, article: pywikibot.Page, revs_list: list[pywikibot.page._revision], print_info: bool) \
            -> list[tuple[pywikibot.page._revision, pywikibot.page._revision, set[str]]]:
        if print_info: print("\tStarting to analyse each revision within time range for reverts\n")

        reverted_users_set = set[str]()
        reverts_list: list[tuple[pywikibot.page._revision, pywikibot.page._revision, set[str]]] = []
        revs_with_revert_idxs_set = set[int]()

        # Traverse revisions list looking for reverts (skipping self-reverts) and store them when found
        for i in range(0, len(revs_list)-2):
            rev_i = revs_list[i]
            rev_i_user = cls.__extract_rev_user(revs_list[i+1])

            # Skip this revision if it has already been counted in a previous revert or is part of anti-vandalism bots'
            # activity
            if i in revs_with_revert_idxs_set or cls.__is_known_bot(rev_i_user):
                continue

            # Add next rev user as possibly reverted user (next rev cannot cause a revert as it is necessary at least
            # an article in between to provoke one, otherwise, this and next revision would be identical)

            reverted_users_set.add(rev_i_user)

            for j in range(i+2, len(revs_list)-1):
                rev_j = revs_list[j]
                rev_j_user = cls.__extract_rev_user(rev_j)

                # Skip known antivandalism bots' activity
                if cls.__is_known_bot(rev_j_user):
                    continue

                if rev_i.get("sha1") == rev_j.get("sha1"):
                    # (Exclude self reverts)
                    if rev_j_user in reverted_users_set:
                        reverted_users_set.remove(rev_j_user)

                    # Store the reverted detected and the idx of the reverting revision to avoid analyzing it later
                    reverts_list.append((rev_i, rev_j, reverted_users_set.copy()))
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
    def __extract_rev_user(rev: pywikibot.page._revision) -> str:
        if rev.get("user") is not None:
            user = rev.get("user")
        else:
            user = rev.get("userhidden") if rev.get("userhidden") is not None else "No user info available"

        return user

    @staticmethod
    def __is_known_bot(user: str) -> bool:
        known_bots = {"SeroBOT", "PatruBot", "AVBOT", "AVdiscuBOT", "Botarel", "CVBOT", "CVNBot"}


    @staticmethod
    def _find_mutual_reverts(article: pywikibot.Page, reverts_list: list[tuple[pywikibot.page._revision,
                             pywikibot.page._revision, set[str]]], print_info: bool) -> list[tuple[tuple[Any, Any, set[str]],
                             tuple[Any, Any, set[str]]]]:
        if print_info: print("\tFiltering reverts keeping mutual ones\n")

        mutual_reverts_list: list[tuple[tuple[pywikibot.page._revision, pywikibot.page._revision, set[str]],
                             tuple[pywikibot.page._revision, pywikibot.page._revision, set[str]]]] = []

        # Traverse reverts list looking for mutual reverts and store them when found
        for i in range(len(reverts_list)):
            revert_1 = reverts_list[i]
            reverser_user = revert_1[1].get("user")

            # For each user reverted, check if it has commited a revert against reverser_user (mutual revert)
            for reverted_user in revert_1[2]:
                for j in range(i + 1, len(reverts_list)):
                    revert_2 = reverts_list[j]

                    if reverted_user == revert_2[1].get("user") and revert_2[2].__contains__(reverser_user):
                        mutual_reverts_list.append((revert_1, revert_2))

            if print_info:
                clear_n_lines(1)
                print(f"\t\tReverts analyzed: {i+1}, total nº of mutual reverts detected: {len(mutual_reverts_list)}")

        return mutual_reverts_list


    @classmethod
    def __calculate_nr_values(cls, mutual_reverts_list: list[tuple[tuple[pywikibot.page._revision,
                              pywikibot.page._revision, set[str]], tuple[pywikibot.page._revision,
                              pywikibot.page._revision, set[str]]]], revs_list: list[pywikibot.page._revision]) \
                              -> tuple[list[int], dict[str, int]]:
        # Traverse mutual reverts list calculating the Nr value for each pair of mutual reversers
        # Nr value is calculated as the minimum of the total edits of each reverser. While doing so,
        # max Nr value is saved to remove this outlay from the set of Nr values
        max_nr = 0
        idx_max_nr = 0
        nr_values_list: list[int] = []
        mutual_reversers_dict: dict[str, int] = {}

        for n in range(len(mutual_reverts_list)):
            mutual_revert = mutual_reverts_list[n]

            reverser_user_i = mutual_revert[0][1].get("user")
            reverser_user_j = mutual_revert[1][1].get("user")

            # Count n_edits of reverser_user_i and j, if we have not stored already their edits number
            if mutual_reversers_dict.get(reverser_user_i) is None:
                mutual_reversers_dict[reverser_user_i] = cls._count_user_edits(reverser_user_i, revs_list)
            n_edits_i = mutual_reversers_dict[reverser_user_i]

            if mutual_reversers_dict.get(reverser_user_j) is None:
                mutual_reversers_dict[reverser_user_j] = cls._count_user_edits(reverser_user_j, revs_list)
            n_edits_j = mutual_reversers_dict[reverser_user_j]

            # Calculate Nr value for this mutual revert
            nr_value = min(n_edits_i, n_edits_j)
            nr_values_list.append(nr_value)

            # Update max Nr if necessary
            if max_nr < nr_value:
                max_nr = nr_value
                idx_max_nr = len(nr_values_list) - 1

        # Once finished drop max Nr value from list and associated user from reversers dictionary
        if len(nr_values_list) > 0:
            nr_values_list.pop(idx_max_nr)
            mutual_reversers_dict.pop(reverser_user_i)

        return nr_values_list, mutual_reversers_dict


    @staticmethod
    def _count_user_edits(user: Any, revs_list: list[pywikibot.page._revision]) -> int:
        n_edits = 0

        for rev in revs_list:
            if user == rev.get("user"):
                n_edits += 1

        return n_edits


    @staticmethod
    def __calculate_edit_war_value(n_mutual_reversers: int, nr_values_list: list[int]) -> int:

        edit_war_value = 0

        for nr_value in nr_values_list:
            edit_war_value += nr_value

        edit_war_value = n_mutual_reversers * edit_war_value

        return edit_war_value


    @classmethod
    def print_pages_with_tags(cls, articles_with_edit_war_info_dict: dict[pywikibot.Page, ArticleEditWarInfo]):
        print("[ID] PAGE TITLE --> URL --> EDIT_WAR")
        i = 0
        n_edit_wars = 0

        for i, article_info in enumerate(articles_with_edit_war_info_dict.values(), start=1):
            tag = article_info.is_in_edit_war
            value = article_info.edit_war_over_time_list[0]
            if tag:
                n_edit_wars += 1

            print(f'[{i}] {article_info.article.title()} --> {article_info.article.full_url()} --> {tag} '
                  f'({value}/{cls.EDIT_WAR_THRESHOLD})')

        print(f'\nArticles analyzed: {i} \nArticles with edit war: {n_edit_wars}')