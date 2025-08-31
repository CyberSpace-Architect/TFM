import re
import os
import plotext as plt
import numpy as np
import getpass
import subprocess

from shutil import get_terminal_size
from datetime import datetime, timezone, timedelta
from os import system as os_system
from platform import system as platform_system
from sys import stdout
from ctypes import windll

from app.utils.common import Singleton


def ask_valid_date(msg: str, default_value: datetime, date_format: str) -> datetime:
    date = input(msg)

    while date != "" and not validate_date_format(date, date_format):
        date = input("Invalid date, please, introduce a valid one ")

    if date == "":
        date = default_value
    else:
        date = datetime.strptime(date, date_format)

    return date


def validate_date_format(date:str, date_format:str) -> bool:
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


def validate_idx(idx: str, min_value: int, max_value: int) -> str:
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


def validate_idx_in_list(idx: str, valid_values_list: list[int]) -> str:
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


def clear_n_lines(n: int):
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


def create_scheduled_task(task_name: str, frequency: int, execution_path: str, script_path: str, args: str):

    if platform_system() == 'Windows':
        user = getpass.getuser()
        start_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT10:00")
        description = ("Scheduled task for automatic detection of edit wars for articles within a session of "
                       "Conflict Watcher program")

        xml_template = f"""<?xml version="1.0" encoding="UTF-16"?>
            <Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
              <RegistrationInfo>
                <Description>{description}</Description>
              </RegistrationInfo>
              <Triggers>
                <CalendarTrigger>
                  <StartBoundary>{start_date}</StartBoundary>
                  <Enabled>true</Enabled>
                  <ScheduleByDay>
                    <DaysInterval>{frequency}</DaysInterval>
                  </ScheduleByDay>
                </CalendarTrigger>
                <LogonTrigger>
                  <Enabled>true</Enabled>
                </LogonTrigger>
              </Triggers>
              <Principals>
                <Principal id="Author">
                  <UserId>{user}</UserId>
                  <LogonType>InteractiveToken</LogonType>
                  <RunLevel>LeastPrivilege</RunLevel>
                </Principal>
              </Principals>
              <Settings>
                <StartWhenAvailable>true</StartWhenAvailable>
                <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
              </Settings>
              <Actions Context="Author">
                <Exec>
                  <Command>{script_path}</Command> 
                  <Arguments>{args}</Arguments>
                  <WorkingDirectory>"{execution_path}"</WorkingDirectory>
                </Exec>
              </Actions>
            </Task>"""

        # <Command> python -m app.main </Command>   for development only add this to Exec field on XML conf above

        folder = get_monitoring_folder()
        xml_path = os.path.join(folder, f'{task_name}_conf.xml')

        with open(xml_path, "w", encoding="utf-16") as f:
            f.write(xml_template)

        # Comando schtasks
        cmd = f'/Create /TN "{task_name}" /XML "{xml_path}" /F'

        # Ask user to confirm task creation (UAC confirmation)
        input("Now, a confirmation screen will appear to allow the creation of the scheduled task, please confirm. ")
        windll.shell32.ShellExecuteW(None, "runas", "schtasks.exe", cmd, None, 1)

    else:
        delay_after_login = 5 # minutes
        # command = f'python3 {script_path} {args}'     For development only
        command = f'{script_path} {args}'

        anacron_conf = f'{frequency}\t{delay_after_login}\t{task_name}\t{command}\n'
        anacron_file = os.path.expanduser("~/.anacrontab")

        lines = []

        if os.path.exists(anacron_file):
            with open(anacron_file, "r") as f:
                lines = f.readlines()

        lines = [l for l in lines if f'{task_name}' not in l]

        with open(anacron_file, "w") as f:
            f.writelines(lines)
            f.write(anacron_conf)


def get_monitoring_folder():
    folder = os.path.join(os.path.dirname(__file__), "monitoring")
    if not os.path.exists(folder):
        os.makedirs(folder)
    return folder


def generate_system_notification(app: str, title: str, msg: str):
    if platform_system() == "Windows":
        # Import only if system is Windows to avoid errors
        from winotify import Notification, audio

        n = Notification(app_id=app,
                         title=title,
                         msg=msg,
                         duration="short")  # 5 seconds
        n.set_audio(audio.Default, loop=False)
        n.show()
    else:
        # Linux system
        subprocess.run(["notify-send",
                        "-a ", app,
                        title,
                        msg,
                        "-t", "5000"])  # 5 seconds


def delete_scheduled_task(session_id: str):
    if platform_system() == 'Windows':
        task_name = f'conflict_watcher_session_{session_id}_monitor'
        folder = get_monitoring_folder()
        xml_path = os.path.join(folder, f'{task_name}_conf.xml')
        cmd = f'schtasks /Delete /TN "{task_name}" /F'

        # Delete task from Windows Task Scheduler
        windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", f'/c {cmd}', None, 1)

        # Delete XML if exists
        if os.path.exists(xml_path):
            try:
                os.remove(xml_path)
            except OSError as e:
                print(f"XML file {e} could not be deleted.")
    else:
        anacron_file = os.path.expanduser("~/.anacrontab")

        if os.path.exists(anacron_file):
            task_name = f'conflict_watcher_session_{session_id}_monitor'

            with open(anacron_file, "r") as f:
                lines = f.readlines()

            lines = [l for l in lines if task_name not in l]

            with open(anacron_file, "w") as f:
                f.writelines(lines)