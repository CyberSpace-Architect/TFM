import re
import pywikibot

from datetime import datetime, timezone
from os import system as os_system
from platform import system as platform_system
from sys import stdout


# Shared dictionary for multi-purposes (right now only counting printed lines to remove)
_shared_dict = {}

# Dictionary of articles with associated info (typing without from article_edit_war_info import ArticleEditWarInfo to
# avoid circular imports)
_articles_with_edit_war_info_dict: dict[pywikibot.Page, object] = {}

def validate_date_format(date:str, format:str):
    valid_date_format = False

    if date is not None and date != "":
        try:
            date = datetime.strptime(date, format)
            valid_date_format = True
        except ValueError:
            valid_date_format = False

    return valid_date_format


def datetime_to_iso(date: datetime) -> str:
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    else:
        date = date.astimezone(timezone.utc)
    return date.strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_idx(idx:str, min_value:int, max_value:int) -> int:
    valid_idx = False

    while not valid_idx:
        idx = re.sub(r"\s+", "", idx)
        if not idx.isdigit() or int(idx) < min_value or int(idx) > max_value:
            idx = input("Invalid index, please select a valid one ")
            _shared_dict["lines_to_remove"] = _shared_dict.get("lines_to_remove", 0) + 1
        else:
            valid_idx = True

    return idx


def clear_n_lines(n):
    """
    Delete n lines from terminal

    :param n: number of lines
    """
    for _ in range(n):
        stdout.write("\033[F")
        stdout.write("\033[K")
    stdout.flush()


def clear_terminal():
    if platform_system() == "Windows":
        os_system("cls")
    else:
        os_system("clear")

    _shared_dict["lines_to_remove"] = 0
