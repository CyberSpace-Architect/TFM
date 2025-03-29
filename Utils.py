from datetime import datetime


def validate_date_format(date:str, format:str):
    valid_date_format = False

    if date is not None and date != "":
        try:
            date = datetime.strptime(date, format)
            valid_date_format = True
        except ValueError:
            valid_date_format = False

    return valid_date_format

def validate_idx(idx:str, min_value:int, max_value:int):
    valid_idx = False

    while not valid_idx:
        if not idx.isdigit() or int(idx) <= min_value or int(idx) > max_value:
            idx = input("Invalid index, please select a valid one ")
        else:
            idx = int(idx) - 1
            valid_idx = True

    return idx
