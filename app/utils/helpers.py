import re
import os
import plotext as plt
import numpy as np

from shutil import get_terminal_size
from datetime import datetime, timezone
from os import system as os_system
from platform import system as platform_system
from sys import stdout

from app.utils.common import Singleton


def ask_valid_date(msg: str, default_value: datetime, date_format: str):
    date = input(msg)

    while date != "" and not validate_date_format(date, date_format):
        date = input("Invalid date, please, introduce a valid one ")

    if date == "":
        date = default_value
    else:
        date = datetime.strptime(date, date_format)

    return date


def validate_date_format(date:str, date_format:str):
    valid_date_format = False

    if date is not None and date != "":
        try:
            datetime.strptime(date, date_format)
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


def validate_idx(idx:str, min_value:int, max_value:int) -> str:
    valid_idx = False

    while not valid_idx:
        idx = re.sub(r"\s+", "", idx)
        if not idx.isdigit() or int(idx) < min_value or int(idx) > max_value:
            idx = input("Invalid index, please select a valid one ")
            shared_dict = Singleton().shared_dict
            shared_dict["lines_to_remove"] = shared_dict.get("lines_to_remove", 0) + 1
        else:
            valid_idx = True

    return idx


def validate_idx_in_list(idx:str, valid_values_list:list[int]) -> str:
    valid_idx = False

    while not valid_idx:
        idx = re.sub(r"\s+", "", idx)
        if not idx.isdigit() or int(idx) not in valid_values_list:
            idx = input("Invalid index, please select a valid one ")
            shared_dict = Singleton().shared_dict
            shared_dict["lines_to_remove"] = shared_dict.get("lines_to_remove", 0) + 1
        else:
            valid_idx = True

    return idx


def print_delim_line(delim: str):
    width = get_terminal_size().columns
    print("\n" + delim * width + "\n")


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

    Singleton().shared_dict["lines_to_remove"] = 0


def ask_yes_or_no_question(question: str) -> bool:
    answer = False

    want_to_save = re.sub(r'\s+', '', input(question).lower())

    while want_to_save not in {"y", "yes", "n", "no"}:
        want_to_save = re.sub(r'\s+', '', input("Invalid response, please write y or yes if "
                                                "you want to, n or no otherwise ").lower())
        clear_n_lines(1)

    if want_to_save in {"y", "yes"}:
        answer = True

    return answer


def plot_graph(title: str, x_label: str, y_label: str, x_vals: list[str], y_vals: list[int]):
    # Clear previous graph configuration
    plt.clear_figure()

    # Set graph's dimensions
    size = os.get_terminal_size()
    width = size.columns
    height = size.lines
    plt.plot_size(width=width, height=min(60, height - 5))

    # Prepare and assign Y axis values
    min_y = min(y_vals)
    max_y = max(y_vals)
    yticks = list(np.linspace(min_y, max_y, 10))
    yticks = [int(round(t)) for t in yticks]
    yticks = sorted(set(yticks))  # Delete duplicates
    plt.yticks(yticks)

    # Assign X axis values
    plt.xticks(x_vals)

    # Set graph's visual configuration
    plt.canvas_color("black")
    plt.axes_color("black")
    plt.ticks_color("white")
    plt.title(title)
    plt.xlabel(x_label)
    plt.ylabel(y_label)

    # Print graph
    plt.bar(x_vals, y_vals, color="blue")
    plt.show()

