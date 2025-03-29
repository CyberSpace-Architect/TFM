from datetime import datetime
from typing import Iterable

import pywikibot
import ppdeep
from sortedcontainers import SortedSet

import WikiCrawler


class EditWarDetector(object):
    EDIT_WAR_THRESHOLD = 100

    articles_set:SortedSet[pywikibot.Page] = None
    rev_start_date:datetime = None
    rev_end_date:datetime = None
    articles_with_edit_war_tags: dict[pywikibot.Page, bool] = None

    #editors_map : dict = None
    #mutual_reverts_map : dict[none,none] = None


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



    def is_article_in_edit_war(self, article: pywikibot.Page):
        edit_war = False

        print("\tRequesting revisions within time range to Wikipedia")
        revs = WikiCrawler.WikiCrawler.revisions_within_range(article, self.rev_start_date, self.rev_end_date)
        print(f"\tRevisions received, number of revisions {len(revs)}")
        revisions_and_fuzzy_hashes_list = []
        reverts_with_hashes_list = []
        mutual_reverts_list = []
        mutual_reversers_dict = {}
        nr_values_list = []

        #debug_idx = 1
        # Calculate fuzzy hash of every revision and store them in a list
        for rev in revs:
            #print(debug_idx)
            #debug_idx += 1
            revisions_and_fuzzy_hashes_list.append((rev, ppdeep.hash(str(rev))))

        print("\tStarting to analyse each revision within time range for reverts")
        n_reverts = 0
        # Traverse revisions list looking for reverts (skipping self-reverts) and store them when found
        for i in range(len(revisions_and_fuzzy_hashes_list)-1):
            revision_and_hash1 = revisions_and_fuzzy_hashes_list[i]
            debug_idx = 1
            for j in range(i+1, len(revisions_and_fuzzy_hashes_list)):
                #print(debug_idx)
                #debug_idx += 1
                revision_and_hash2 = revisions_and_fuzzy_hashes_list[j]

                if ppdeep.compare(revision_and_hash1[1], revision_and_hash2[1]) >= 90:
                    if revision_and_hash1[0].user == revision_and_hash2[0].user:
                        reverts_with_hashes_list.append((revision_and_hash1, revision_and_hash2))
                        n_reverts += 1

            print(f"\t\tRevisions_analyzed: {debug_idx}, total nº of reverts detected: {n_reverts}")
            debug_idx += 1

        # Traverse reverts list looking for mutual reverts and store them when found
        for i in range(len(reverts_with_hashes_list)-1):
            revert_with_hashes1 = reverts_with_hashes_list[i]
            user_i = revert_with_hashes1[0][0].user
            user_j = revert_with_hashes1[1][0].user

            for j in range(i+1, len(reverts_with_hashes_list)):
                revert_with_hashes2 = reverts_with_hashes_list[j]

                if user_j == revert_with_hashes2[0][0].user and user_i == revert_with_hashes2[1][0].user:
                    mutual_reverts_list.append((revert_with_hashes1, revert_with_hashes2))

        max_nr = 0
        idx_max_nr = 0

        # Traverse mutual reverts list calculating the Nr value for each pair of mutual reversers.
        # Nr value is calculated as the minimum of the total edits of each reverser on the revision and fuzzy hash list
        # While doing so, max Nr value is saved to remove this outlay from the set of Nr values
        for n in range(len(mutual_reverts_list)):
            mutual_rev = mutual_reverts_list[n]

            user_i = mutual_rev[0][0][0].user
            user_j = mutual_rev[0][1][0].user

            # Count n_edits of user_i
            n_edits_i = 0
            if mutual_reversers_dict.get(user_i) is None:
                for revision_and_fuzzy_hash in revisions_and_fuzzy_hashes_list:
                    if user_i == revision_and_fuzzy_hash[0].user:
                        n_edits_i += 1
                mutual_reversers_dict[user_i] = n_edits_i
            else:
                n_edits_i = mutual_reversers_dict[user_i]

            # Count n_edits of user_j
            n_edits_j = 0
            if mutual_reversers_dict.get(user_j) is None:
                for revision_and_fuzzy_hash in revisions_and_fuzzy_hashes_list:
                    if user_j == revision_and_fuzzy_hash[0].user:
                        n_edits_j += 1
                mutual_reversers_dict[user_j] = n_edits_j
            else:
                n_edits_j = mutual_reversers_dict[user_j]

            # Calculate Nr value for this mutual revert
            nr_value = min(n_edits_i, n_edits_j)
            nr_values_list.append(nr_value)

            # Update max Nr if necessary
            if max_nr < nr_value:
                max_nr = nr_value
                idx_max_nr = n

        # Drop max Nr value from mutual reverts list
        if len(mutual_reverts_list) > 0:
            mutual_reverts_list.pop(idx_max_nr)

            # Calculate E value as the total number of mutual reversers (length of mutual reversers' dict)
            n_mutual_reversers = len(mutual_reversers_dict)

            # Calculate edit_war value as the sum of Nr values multiplied by the E value
            edit_war_value = 0
            for nr_value in nr_values_list:
                edit_war_value += nr_value

            edit_war_value = n_mutual_reversers * edit_war_value

            # Alert of edit war in the article if the value surpasses the threshold
            if edit_war_value > self.EDIT_WAR_THRESHOLD:
                edit_war = True

        print(f"Analysis finished, article with edit war?: {edit_war}")

        return edit_war


    def print_pages_with_tags(self):
        print("[ID] PAGE TITLE --> URL --> EDIT_WAR\n")
        idx = 0
        n_edit_wars = 0

        for article, tag in self.articles_with_edit_war_tags.items():
            idx += 1
            if tag:
                n_edit_wars += 1

            print(f'[{idx}] {article.title()} --> {article.full_url()} --> {tag}')

        print(f'\nArticles analyzed: {idx}\nArticles with edit war: {n_edit_wars}')