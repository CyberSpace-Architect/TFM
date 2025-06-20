import re

import pywikibot
from datetime import datetime
from typing import Iterable, Any, LiteralString
from sortedcontainers import SortedSet

from Utils import datetime_to_iso, clear_n_lines



class EditWarDetector(object):
    EDIT_WAR_THRESHOLD = 100

    articles_set:SortedSet[pywikibot.Page] = None
    rev_start_date:datetime = None
    rev_end_date:datetime = None
    articles_with_edit_war_tags: dict[pywikibot.Page, bool] = None


    def __init__(self, articles_set:SortedSet[pywikibot.Page], rev_start_date:datetime, rev_end_date:datetime):
        self.articles_set = articles_set
        self.rev_start_date = rev_start_date
        self.rev_end_date = rev_end_date
        self.articles_with_edit_war_tags: dict[pywikibot.Page, bool] = {}


    def set_articles_set(self, articles_set):
        self.articles_set = articles_set


    def detect_edit_wars_in_set(self):
        print("\n===> Starting detection of edit wars...")
        for article in self.articles_set:
            print(f"\nAnalyzing article {article.title()}")
            edit_war_tag = self.is_article_in_edit_war(article)
            self.articles_with_edit_war_tags[article] = edit_war_tag


    def is_article_in_edit_war(self, article: pywikibot.Page) -> bool:
        edit_war = False

        print("\tRequesting revisions to Wikipedia")
        revs_list = self.get_full_revisions_in_range(article, self.rev_start_date, self.rev_end_date)
        print(f"\t\tRevisions received, number of revisions within time range: {len(revs_list)}")

        # Find and store all reverts
        reverts_list = self.find_reverts(revs_list)

        # Filter reverts and keep only mutual ones
        mutual_reverts_list = self.find_mutual_reverts(reverts_list)

        # Calculate Nr value (min of nº edits) of each pair of mutual reversers from mutual reverts list,
        # a dictionary with the nº of edits for each mutual reversers is retrieved too
        nr_values_list, mutual_reversers_dict = self.calculate_nr_values(mutual_reverts_list, revs_list)

        # Calculate E value as the total number of mutual reversers (length of mutual reversers' dict)
        n_mutual_reversers = len(mutual_reversers_dict)

        # Calculate edit_war value as the sum of Nr values multiplied by the E value
        edit_war_value = self.calculate_edit_war_value(n_mutual_reversers, nr_values_list)

        # Alert of edit war in the article if the value surpasses the threshold
        if edit_war_value > self.EDIT_WAR_THRESHOLD:
            edit_war = True

        print(f"Analysis finished, article with edit war?: {edit_war}")

        return edit_war


    def get_full_revisions_in_range(self, article: pywikibot.Page, start: datetime, end: datetime) -> list[pywikibot.Page]:
        site = pywikibot.Site("es", "wikipedia")

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

            request = site._request(**params)
            data = request.submit()

            page_id = next(iter(data["query"]["pages"]))
            revs_list.extend(data["query"]["pages"][page_id].get("revisions", []))

            if "continue" in data:
                rvcontinue = data["continue"]["rvcontinue"]
            else:
                break

        return revs_list


    def find_reverts(self, revs_list: list[pywikibot.page._revision]) \
            -> list[tuple[pywikibot.page._revision, pywikibot.page._revision, set[str]]]:
        print("\tStarting to analyse each revision within time range for reverts\n")
        reverts_list: list[tuple[pywikibot.page._revision, pywikibot.page._revision, set[str]]] = []
        reverted_users_set = set[str]()

        # Traverse revisions list looking for reverts (skipping self-reverts) and store them when found
        for i in range(0, len(revs_list)-2):
            rev_i = revs_list[i]
            reverted_users_set.add(revs_list[i+1]["user"])

            for j in range(i+2, len(revs_list)-1):
                rev_j = revs_list[j]

                if rev_i.get("sha1") == rev_j.get("sha1"):
                    # (Exclude self reverts)
                    if reverted_users_set.__contains__(rev_j.get("user")):
                        reverted_users_set.remove(rev_j.get("user"))

                    reverts_list.append((rev_i, rev_j, reverted_users_set.copy()))

                # Rev_j is a revert to rev_i, so user from rev_j has commited a revert against all users of
                # revisions from i+1 to j-1, so we add all possibly reverted users to set
                #print("Añado usuario: " + str(rev_j["user"]))
                reverted_users_set.add(rev_j.get("user"))

            # Reset set after checking all possible reverts for revision i
            reverted_users_set.clear()

            clear_n_lines(1)
            print(f"\t\tRevisions analyzed: {i + 1}, total nº of reverts detected: {len(reverts_list)}")

        return reverts_list


    def find_mutual_reverts(self, reverts_list: list[tuple[pywikibot.page._revision, pywikibot.page._revision, set[str]]]) \
                            -> list[tuple[tuple[Any, Any, set[str]], tuple[Any, Any, set[str]]]]:
        print("\tFiltering reverts keeping mutual ones\n")
        mutual_reverts_list: list[tuple[tuple[pywikibot.page._revision, pywikibot.page._revision, set[str]], \
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

            clear_n_lines(1)
            print(f"\t\tReversers analyzed: {i+1}, total nº of mutual reverts detected: {len(mutual_reverts_list)}")

        return mutual_reverts_list


    def calculate_nr_values(self,
                            mutual_reverts_list: list[tuple[tuple[pywikibot.page._revision, pywikibot.page._revision, set[str]], \
                                    tuple[pywikibot.page._revision, pywikibot.page._revision, set[str]]]],
                            revs_list: list[pywikibot.page._revision]) -> tuple[list[int], dict[Any, int]]:
        # Traverse mutual reverts list calculating the Nr value for each pair of mutual reversers
        # Nr value is calculated as the minimum of the total edits of each reverser. While doing so,
        # max Nr value is saved to remove this outlay from the set of Nr values
        max_nr = 0
        idx_max_nr = 0
        nr_values_list: list[int] = []
        mutual_reversers_dict: dict[Any, int] = {}

        for n in range(len(mutual_reverts_list)):
            mutual_revert = mutual_reverts_list[n]

            reverser_user_i = mutual_revert[0][1].get("user")
            reverser_user_j = mutual_revert[1][1].get("user")

            # Count n_edits of reverser_user_i and j, if we have not stored them already their edits number
            n_edits_i = self.count_user_edits(reverser_user_i, revs_list) if mutual_reversers_dict.get(reverser_user_i) is None else 0
            mutual_reversers_dict[reverser_user_i] = n_edits_i
            n_edits_j = self.count_user_edits(reverser_user_j, revs_list) if mutual_reversers_dict.get(reverser_user_j) is None else 0
            mutual_reversers_dict[reverser_user_j] = n_edits_j

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

        return nr_values_list, mutual_reversers_dict


    def count_user_edits(self, user: Any, revs_list: list[pywikibot.page._revision]) -> int:
        n_edits = 0

        for rev in revs_list:
            if user == rev.get("user"):
                n_edits += 1

        return n_edits


    def calculate_edit_war_value(self, n_mutual_reversers: int, nr_values_list: list[int]) -> int:
        edit_war_value = 0

        for nr_value in nr_values_list:
            edit_war_value += nr_value

        edit_war_value = n_mutual_reversers * edit_war_value

        return edit_war_value


    def print_pages_with_tags(self):
        print("[ID] PAGE TITLE --> URL --> EDIT_WAR")
        idx = 0
        n_edit_wars = 0

        for article, tag in self.articles_with_edit_war_tags.items():
            idx += 1
            if tag:
                n_edit_wars += 1

            print(f'[{idx}] {article.title()} --> {article.full_url()} --> {tag}')

        print(f'\nArticles analyzed: {idx}\nArticles with edit war: {n_edit_wars}')