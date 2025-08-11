import os
import re
import sqlite3

from contextlib import contextmanager
from datetime import datetime, timezone
from sqlite3 import Connection
from typing import Any, Tuple

from app.info_containers.article_edit_war_info import ArticleEditWarInfo
from app.info_containers.local_page import LocalPage
from app.info_containers.local_revision import LocalRevision
from app.info_containers.local_user import LocalUser
from app.utils.helpers import print_delim_line, clear_terminal, clear_n_lines, datetime_to_iso, ask_yes_or_no_question

CREATE_TABLE_SQL_DICT: dict[str, str] = {
    "sessions" : """CREATE TABLE IF NOT EXISTS sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        timestamp TEXT NOT NULL
                    );
    """,
    "users" : """CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        site TEXT,
                        is_registered INTEGER,
                        is_blocked INTEGER,
                        registration_date TEXT,
                        edit_count INTEGER,
                        asn TEXT,
                        asn_description TEXT,
                        network_address TEXT,
                        network_name TEXT,
                        network_country TEXT,
                        registrants_info TEXT
                 ); 
    """,
    "articles" : """CREATE TABLE IF NOT EXISTS articles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        pageid INTEGER NOT NULL,
                        session INTEGER NOT NULL,
                        title TEXT NOT NULL,
                        url TEXT NOT NULL,
                        site TEXT,
                        namespace TEXT,
                        content_model TEXT,
                        text TEXT,
                        discussion_page_title TEXT,
                        discussion_page_url TEXT,
                        discussion_page_text TEXT,
                        FOREIGN KEY (session) REFERENCES sessions(id) ON DELETE CASCADE
                    );
    """,
    "revisions" : """CREATE TABLE IF NOT EXISTS revisions (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            revid INTEGER NOT NULL,
                            article INTEGER NOT NULL, 
                            timestamp TEXT NOT NULL,
                            user INTEGER,
                            text TEXT,
                            size INTEGER,
                            tags TEXT,
                            comment TEXT,
                            sha1 TEXT,
                            FOREIGN KEY (article) REFERENCES articles(id) ON DELETE CASCADE,
                            FOREIGN KEY (user) REFERENCES users(id)
                     );
    """,
    "edit_war_analysis_periods" : """CREATE TABLE IF NOT EXISTS edit_war_analysis_periods (
                                          id INTEGER PRIMARY KEY AUTOINCREMENT,
                                          article INTEGER NOT NULL,
                                          start_date TEXT NOT NULL,
                                          end_date TEXT NOT NULL,
                                          FOREIGN KEY (article) REFERENCES articles(id) ON DELETE CASCADE
                                    ); 
    """,
    "edit_war_values" : """CREATE TABLE IF NOT EXISTS edit_war_values (
                                  period INTEGER,
                                  date TEXT,
                                  value INTEGER NOT NULL,
                                  PRIMARY KEY (period, date),
                                  FOREIGN KEY (period) REFERENCES edit_war_analysis_periods(id) ON DELETE CASCADE
                            ); 
    """,
    "reverts" : """CREATE TABLE IF NOT EXISTS reverts (
                          revertant_rev INTEGER,
                          reverted_rev INTEGER,
                          PRIMARY KEY (revertant_rev, reverted_rev),
                          FOREIGN KEY (revertant_rev) REFERENCES revisions(id) ON DELETE CASCADE,
                          FOREIGN KEY (reverted_rev) REFERENCES revisions(id) ON DELETE CASCADE
                    ); 
    """,
    "reverted_user_pairs" : """CREATE TABLE IF NOT EXISTS reverted_user_pairs (
                                      revertant_rev INTEGER,
                                      reverted_rev INTEGER,
                                      user INTEGER,
                                      PRIMARY KEY (revertant_rev, reverted_rev, user),
                                      FOREIGN KEY (revertant_rev, reverted_rev) REFERENCES reverts(revertant_rev, reverted_rev) ON DELETE CASCADE,
                                      FOREIGN KEY (user) REFERENCES users(id) ON DELETE CASCADE
                                ); 
    """,
    "mutual_reverts" : """CREATE TABLE IF NOT EXISTS mutual_reverts (
                                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                                      revertant_rev_1 INTEGER,
                                      reverted_rev_1 INTEGER,
                                      revertant_rev_2 INTEGER,
                                      reverted_rev_2 INTEGER,
                                      FOREIGN KEY (revertant_rev_1, reverted_rev_1) REFERENCES reverts(revertant_rev, reverted_rev) ON DELETE CASCADE,
                                      FOREIGN KEY (revertant_rev_2, reverted_rev_2) REFERENCES reverts(revertant_rev, reverted_rev) ON DELETE CASCADE
                          ); 
    """,
    "mutual_reverters_activities" : """CREATE TABLE IF NOT EXISTS mutual_reverters_activities (
                                       user INTEGER,
                                       period INTEGER,
                                       n_mutual_reverts INTEGER,
                                       PRIMARY KEY (user, period),
                                       FOREIGN KEY (user) REFERENCES users(id) ON DELETE CASCADE,
                                       FOREIGN KEY (period) REFERENCES edit_war_analysis_periods(id) ON DELETE CASCADE
                                       ); 
    """,
}

DELETE_SEQUENCES: str = "DELETE FROM sqlite_sequence WHERE name = (?);"


@contextmanager
def sqlite_connection(db: str, uri: bool = False):
    # Create connection to specified database
    conn = sqlite3.connect(db, uri=uri)

    conn.enable_load_extension(False)   # Disable unnecessary and insecure feature
    try:
        # Returned connection
        yield conn
    finally:
        # No matter what, we make sure that connection ends up closing
        conn.close()


def init_db(conn: Connection):
    clear_terminal()
    print_delim_line("#")
    print("Mounting database...\n")

    # Activate foreign keys as they are disabled by default
    conn.execute("PRAGMA foreign_keys = ON")

    # Iterate over dict executing sentences to create db tables
    for table, sql_statement in CREATE_TABLE_SQL_DICT.items():
        create_table_if_not_exists(conn, table, sql_statement)

    # Create and index over user reference, since no cascade deletion occurs in user
    conn.execute("CREATE INDEX IF NOT EXISTS revision_user_idx ON revisions(user);")

    input("\nDatabase mounted, press Enter to continue ")


def reset_db(conn: Connection):
    # Create cursor to the db using the provided connection
    cursor = conn.cursor()

    try:
        print("\nDeleting previous database...")

        # Drop each table
        for table in reversed(CREATE_TABLE_SQL_DICT.keys()):
            cursor.execute(f"DROP TABLE {table};")
            print(f"\tTable '{table}' deleted")

        # Recreate db iterating once more over dict with sql sentences to create tables
        print("\nRecreating database...")
        for table, sql_statement in CREATE_TABLE_SQL_DICT.items():
            create_table_if_not_exists(conn, table, sql_statement)

        input("\nDatabase reset, press Enter to continue ")

        conn.commit()
    finally:
        # No matter what, we ensure cursor end up closing
        cursor.close()


def create_table_if_not_exists(conn: Connection, table: str, create_table_sql_statement: str, show_info: bool = True):
    # Create cursor to the db using the provided connection
    cursor = conn.cursor()

    try:
        # Check if table exists and inform of the action depending on show_info value
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table,))

        if not cursor.fetchone():
            if show_info:
                print(f"\t==> Table '{table}' not found, creating it...")
            cursor.execute(create_table_sql_statement)

            # Commit changes
            conn.commit()
        else:
            if show_info:
                print(f"\t==> Table '{table}' already exists.")

    finally:
        # No matter what, we ensure cursor end up closing
        cursor.close()


def add_to_db_table(conn: Connection, table: str, column_names: str, item: tuple) -> int | None:
    # Create cursor to the db using the provided connection
    cursor = conn.cursor()

    try:
        # Create a safe SQL sentence (using placeholders for values) and execute it
        placeholders = ", ".join(["?"] * len(item))
        cursor.execute(f"INSERT INTO {table} ({column_names}) VALUES ({placeholders});", item)

        # Commit changes
        conn.commit()

        row_id = cursor.lastrowid
    finally:
        # No matter what, we ensure cursor end up closing
        cursor.close()

    return row_id


def fetch_items_from_db(conn: Connection, table: str, where_clause: str = '?=?', where_values: list[str] = None,
                        in_clause:bool = False, additional_where_clauses:list[str] = None,
                        additional_where_values:list[list[str]] = None) -> list | None:

    # By default, WHERE part of the sentence is 1=1 to retrieve all contents
    if where_values is None:
        where_values = ['1', '1']

    # Create cursor to the db using the provided connection
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table,))

        items = None
        if not cursor.fetchone():
            input(f"Table '{table}' not found, cannot fetch data from it ")
        else:
            # If in_clause is True, we will make a request like "...WHERE <attribute> IN ({?,?,?,?...})"
            if in_clause:
                placeholders = ", ".join(["?"] * len(where_values))

                # where_clause must have format " < attribute > IN("
                where_clause += placeholders + ")"

                # If WHERE part is composed of multiple conditions it has to be built with all those conditions
                if additional_where_clauses:
                    for i, additional_where_clause in enumerate(additional_where_clauses):
                        placeholders = ", ".join(["?"] * len(additional_where_values[i]))
                        where_clause += additional_where_clause + placeholders + ")"
                        where_values.extend(additional_where_values[i])

            cursor.execute(f"SELECT rowid,* FROM {table} WHERE {where_clause};", where_values)

            # Fetch filtered items
            items = cursor.fetchall()

            # Commit changes
            conn.commit()

    finally:
        # No matter what, we ensure cursor end up closing
        cursor.close()

    return items


def print_db_table(conn: Connection, table: str) -> list | None:
    # Create cursor to the db using the provided connection
    cursor = conn.cursor()

    try:
        # Fetch contents and print them
        cursor.execute(f"SELECT * FROM {table};")
        rows = print_query_contents(cursor.description, cursor.fetchall(), table)

        # Commit changes
        conn.commit()

    finally:
        # No matter what, we ensure cursor end up closing
        cursor.close()

    return rows


def print_query_contents(description: Tuple[Any], rows: list, table:str = None) -> list:
    # Get names of the columns to be printed
    column_names = [description[0] for description in description]

    # Iterate columns and rows to extract column sizes
    columns_line = ""
    separation_line = ""
    columns_max_length_dict = dict[int, int]()
    extra_column_contents_dict = dict[int, str]()

    # 1º Get terminal size to accommodate columns
    size = os.get_terminal_size()
    spaces_size = len(column_names)
    max_size = int((size.columns - spaces_size) / len(column_names))
    free_space = 0

    # 2º Iterate over each column trying to display it as best as possible depending on the free space available
    for i, column in enumerate(column_names):
        formated_column_length = len(str(column).rstrip())

        # If the space required is less than the one assigned to the column the leftover space is added to the free space
        if formated_column_length <= max_size:
            free_space += max_size - formated_column_length
            columns_max_length_dict[i] = formated_column_length
        # If it is bigger and there's sufficient free space accumulated from previous columns, part of it is
        # used to accommodate this column
        elif formated_column_length < free_space:
            free_space -= formated_column_length - max_size
            columns_max_length_dict[i] = formated_column_length
        # Otherwise, half of the free space available is used on this column trying to accommodate as best as possible,
        # but avoiding wasting all the free space on a single column
        else:
            columns_max_length_dict[i] = max_size + int(free_space/2)
            free_space = int(free_space / 2)

    # 3º Iterate over each row of the query contents trying to display it as best as possible as has been done with columns
    for row in rows:
        free_space = 0  # For each column free space is reset

        for i, value in enumerate(row):
            # Value will be formatted for displaying, so length is also counted after formatting it
            formated_value_length = len(re.sub(r'[\t\n\r]+', '', str(value).rstrip()))
            # Length assigned to column is retrieved from dict
            column_length = columns_max_length_dict[i]

            # Space available is the result of the accumulated free space minus the size assigned to this column compared
            # to the initial max size
            free_space = free_space + (max_size - column_length)

            # If value length is bigger than column size we try to accommodate it
            if formated_value_length > column_length:
                # If there's sufficient free space accumulated from previous columns, part of it is used to accommodate
                # the value of this column
                if formated_value_length < free_space:
                    free_space -= formated_value_length - column_length
                    columns_max_length_dict[i] = formated_value_length
                # Otherwise, half of the free space available is used on this column trying to accommodate as best as
                # possible, but avoiding wasting all the free space on a single column
                else:
                    columns_max_length_dict[i] += int(free_space/2)
                    free_space = int(free_space/2)

    # Once all columns have their sizes as accommodated as possible, line with the column headers (names) is printed
    for i, column in enumerate(column_names):
        column_size = columns_max_length_dict[i]

        # Column line is built with fixed sizes for columns to ensure they are printed aligned
        columns_line += column[:column_size].ljust(column_size) + " "

        # If the column name is bigger than the size assigned to this column, at least an additional line will have to
        # be printed before moving to the next line of contents
        if len(column) > column_size:
            extra_column_contents_dict[i] = column[column_size:]

        # A separation line is printed too dynamically to clearly separate column names from contents
        separation_line += "-" * column_size + " "

    # If the table from which the contents have been extracted is provided, a header line is built and printed first
    if table:
        half_header = "=" * (int((len(separation_line) - len(f" {table.upper()} ")) / 2))
        header_line = half_header + f" {table.upper()} " + half_header
        print(header_line + "\n")

    # Once built, the column line is printed
    print(columns_line)

    # Now, if any column had to print additional lines because the size was not sufficient, they are constructed and
    # printed dynamically
    while len(extra_column_contents_dict.items()) > 0:
        extra_line = ""

        # Each column is iterated checking if additional lines had to be printed for it
        for i, _ in enumerate(column_names):
            column_size = columns_max_length_dict[i]
            extra_column_content = extra_column_contents_dict.get(i)

            # If there's still any extra content to print, as much of it is added to this extra line
            if extra_column_content is not None:
                extra_line += extra_column_content[:column_size].ljust(column_size + 1)

                # If the size is insufficient for all the content remaining as much of it is printed
                if len(extra_column_content) >= column_size:
                    extra_column_contents_dict[i] = extra_column_content[column_size:]
                # Otherwise, the entry is deleted from the dictionary
                else:
                    extra_column_contents_dict.pop(i)
            # If there's no extra content to print for this column it is filled with blank spaces plus the separator
            # space between columns
            else:
                extra_line += " " * (column_size + 1)

        # Each extra line is printed
        print(extra_line)

    # Dict is cleared before populating it with rows contents and the separation line between column names and contents
    # is printed
    extra_column_contents_dict.clear()
    print(separation_line)

    # Finally, all the rows with the contents retrieved from the query are also printed dynamically
    for row in rows:
        # As before, each column is printed and if any value is bigger than column size, those contents are stored
        # to be printed in additional lines
        for i, value in enumerate(row):
            column_size = columns_max_length_dict[i]
            formated_value = re.sub(r'[\t\n\r]+', '', str(value).rstrip())
            print(formated_value[:column_size].ljust(column_size), end=" ")

            if len(formated_value) > column_size:
                extra_column_contents_dict[i] = formated_value[column_size:]
        print("")

        # As before, if any column needs additional lines, they are printed
        while len(extra_column_contents_dict) > 0:
            extra_line = ""

            for i, _ in enumerate(column_names):
                column_size = columns_max_length_dict[i]
                extra_column_content = extra_column_contents_dict.get(i)

                if extra_column_content is not None:
                    extra_line += extra_column_content[:column_size].ljust(column_size + 1)

                    if len(extra_column_content) >= column_size:
                        extra_column_contents_dict[i] = extra_column_content[column_size:]
                    else:
                        extra_column_contents_dict.pop(i)
                else:
                    extra_line += "".ljust(column_size + 1)

            print(extra_line)

        extra_column_contents_dict.clear()

    return rows


def update_db_table(conn: Connection, table: str, set_clause: str, set_values, rowid: str):
    # Create cursor to the db using the provided connection
    cursor = conn.cursor()

    try:
        # Create a safe SQL sentence (using a placeholder for rowid) and execute it
        cursor.execute(f"UPDATE {table} SET {set_clause} WHERE rowid = (?);", (*set_values, rowid))

        # Commit changes
        conn.commit()
    finally:
        # No matter what, we ensure cursor end up closing
        cursor.close()


def delete_from_db_table(conn: Connection, table: str, rowid: int):
    # Create cursor to the db using the provided connection
    cursor = conn.cursor()

    try:
        # Create a safe SQL sentence (using a placeholder for rowid) and execute it
        cursor.execute(f"DELETE FROM {table} WHERE rowid = (?);", (str(rowid),))

        # Check if table becomes empty
        n_rows = cursor.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]

        if n_rows == 0:
            # Delete autoincremental ids if the table becomes empty
            cursor.execute(DELETE_SEQUENCES, (table,))

            # If the last session is deleted, we delete contents from user table too (no cascade restriction, so it
            # has to be manually deleted)
            if table == "sessions":
                cursor.execute("DELETE FROM users;")
                cursor.execute(DELETE_SEQUENCES, ("users",))

        # Commit changes
        conn.commit()
    finally:
        # No matter what, we ensure cursor end up closing
        cursor.close()


def add_or_update_if_exists(conn: Connection, table: str, column_names: str, where_clause:str, where_values: list[str],
                            set_clause: str, set_values: list[str], item:tuple) -> int:
    # Check if the value is already present in the table
    stored = fetch_items_from_db(conn, table, where_clause=where_clause, where_values=where_values)

    # If it is, it has to be updated using its rowid
    if stored:
        rowid = stored[0][0]
        update_db_table(conn, table, set_clause, set_values, rowid)
    # Otherwise, it has to be added as a new entry in the table
    else:
        rowid = add_to_db_table(conn, table, column_names, item)

    return rowid


def is_safe_select(query: str) -> bool:
    """
    Function to check that an arbitrary SELECT query is safe

    :param query:
    :return: bool
    """
    is_safe = False

    # Normalize query (lowercase and remove blank space)
    normalized_query = re.sub(r"\s+", " ", query.strip().lower())

    # Check that it is a select query
    if normalized_query.startswith("select"):
        dangerous_keywords = ["insert", "update", "delete", "drop", "alter", "create",
                              "pragma", "attach", "detach", "load_extension", ";", "--", "#",
                              "writefile", "exec", "replace", "vacuum", "sqlite_master", "sqlite_sequence"]

        # Check that no dangerous keywords are included in the query
        for keyword in dangerous_keywords:
            if keyword in normalized_query:
                break
        else:
            is_safe = True

    return is_safe


def sanitize_and_execute_select(conn: Connection, query: str) -> (Tuple[Any], list[Any]):
    """
    Function to sanitize an arbitrary SELECT query and then execute it

    :param conn:
    :param query:
    :return: (Tuple[Any], list[Any]) | None
    """
    return_tuple = None

    # Create cursor to the db using the provided connection
    cursor = conn.cursor()

    try:
        # Sanitize input
        if not is_safe_select(query):
            input("Unsafe query rejected (Enter to continue) ")

        # Query is execute only after checking that is safe
        else:
            cursor.execute(query)
            description = cursor.description
            results = cursor.fetchall()

            if description is None and results is None:
                print("Search yielded no results ")

            return_tuple = (description, results)

    except sqlite3.OperationalError as e:
        input(f'Operational error: {e} (Enter to continue) ')
    except sqlite3.InterfaceError as e:
        input(f'Parameters error: {e} (Enter to continue) ')
    except sqlite3.Error as e:
        input(f'Unclassified error: {e} (Enter to continue) ')
    finally:
        # No matter what, we ensure cursor end up closing
        cursor.close()

    return return_tuple


def delete_non_referenced_users(conn: Connection):
    """
    Function to delete users that are not referenced by any revision after deletions

    :param conn:
    :return: None
    """

    query = """ DELETE FROM users
                        WHERE NOT EXISTS (
                            SELECT 1
                            FROM revisions
                            WHERE revisions.user = users.id
                        );
            """

    # Create cursor to the db using the provided connection
    cursor = conn.cursor()

    try:
        # Execute query
        cursor.execute(query)

        # Check if table becomes empty
        n_rows = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]

        if n_rows == 0:
            # Delete autoincremental ids if the table becomes empty
            cursor.execute(DELETE_SEQUENCES, ("users",))

        # Commit changes
        conn.commit()
    finally:
        # No matter what, we ensure cursor end up closing
        cursor.close()


def create_temp_session_db(orig_db_conn: Connection, temp_db_conn, session: list):
    print("Creating temporary copy of session data to allow full analysis, please wait... ")

    # Create cursors to both databases
    orig_db_cursor = orig_db_conn.cursor()
    temp_db_cursor = temp_db_conn.cursor()

    try:
        # Database tables list
        tables = ("sessions", "articles", "edit_war_analysis_periods", "edit_war_values", "revisions", "reverts",
                  "mutual_reverts", "users", "reverted_user_pairs", "mutual_reverters_activities")

        # Create tables in temporal database from original schema
        orig_db_cursor.execute(f'SELECT sql FROM sqlite_master WHERE type=? AND name IN {tables}',
                         ("table",))
        create_sqls_list = [row[0] for row in orig_db_cursor.fetchall()]

        for create_sql in create_sqls_list:
            temp_db_cursor.execute(create_sql)

        # Save created tables
        temp_db_conn.commit()

        # Retrieve data from each table of the original database regarding selected session
        # 1º Sessions table (only selected session)
        orig_db_cursor.execute("SELECT * FROM sessions")
        column_names = ','.join(str(column[0]) for column in orig_db_cursor.description if column[0] is not None)

        add_to_db_table(temp_db_conn, "sessions", column_names, tuple(session))
        session_id = session[0]

        # 2º Articles table
        query = "SELECT * FROM articles WHERE session = ?"
        orig_db_cursor.execute(query, str(session_id))

        orig_db_cursor.execute(f'SELECT * FROM articles WHERE session = {session_id}')
        column_names = ','.join(str(column[0]) for column in orig_db_cursor.description if column[0] is not None)
        articles = orig_db_cursor.fetchall()

        if articles:
            articles_ids = [row[0] for row in articles]
            for article in articles:
                add_to_db_table(temp_db_conn, "articles", column_names, tuple(article))
        else:
            return

        # 3º Edit_war_analysis_periods table
        placeholders = ','.join('?' for _ in articles_ids)
        query = f'SELECT * FROM edit_war_analysis_periods WHERE article IN ({placeholders})'
        orig_db_cursor.execute(query, articles_ids)

        column_names = ','.join(str(column[0]) for column in orig_db_cursor.description if column[0] is not None)
        periods = orig_db_cursor.fetchall()

        if periods:
            periods_ids = [row[0] for row in periods]
            for period in periods:
                add_to_db_table(temp_db_conn, "edit_war_analysis_periods", column_names, tuple(period))

            # 4º Edit_war_values table
            placeholders = ','.join('?' for _ in periods_ids)
            query = f'SELECT * FROM edit_war_values WHERE period IN ({placeholders})'
            orig_db_cursor.execute(query, periods_ids)

            column_names = ','.join(str(column[0]) for column in orig_db_cursor.description if column[0] is not None)
            values = orig_db_cursor.fetchall()

            if values:
                for value in values:
                    add_to_db_table(temp_db_conn, "edit_war_values", column_names, tuple(value))

        # 5º Revisions table
        placeholders = ','.join('?' for _ in articles_ids)
        query = f'SELECT * FROM revisions WHERE article IN ({placeholders})'
        orig_db_cursor.execute(query, articles_ids)

        column_names = ','.join(str(column[0]) for column in orig_db_cursor.description if column[0] is not None)
        revs = orig_db_cursor.fetchall()

        if revs:
            revs_ids = [row[0] for row in revs]
            users_ids = [row[4] for row in revs]

            for rev in revs:
                add_to_db_table(temp_db_conn, "revisions", column_names, tuple(rev))

            # 6º Reverts table
            placeholders = ','.join('?' for _ in revs_ids)
            query = f'SELECT * FROM reverts WHERE revertant_rev IN ({placeholders})'
            orig_db_cursor.execute(query, revs_ids)

            column_names = ','.join(str(column[0]) for column in orig_db_cursor.description if column[0] is not None)
            reverts = orig_db_cursor.fetchall()

            if reverts:
                reverts_ids = [row[0] for row in reverts]
                for revert in reverts:
                    add_to_db_table(temp_db_conn, "reverts", column_names, tuple(revert))

                # 7º Mutual reverts table
                placeholders = ','.join('?' for _ in reverts_ids)
                query = f'SELECT * FROM mutual_reverts WHERE revertant_rev_1 IN ({placeholders})'
                orig_db_cursor.execute(query, reverts_ids)

                column_names = ','.join(str(column[0]) for column in orig_db_cursor.description if column[0] is not None)
                mutual_reverts = orig_db_cursor.fetchall()

                if mutual_reverts:
                    for mutual_revert in mutual_reverts:
                        add_to_db_table(temp_db_conn, "mutual_reverts", column_names, tuple(mutual_revert))

            # 8º Users table
            if users_ids:
                placeholders = ','.join('?' for _ in users_ids)
                query = f'SELECT * FROM users WHERE id IN ({placeholders})'
                orig_db_cursor.execute(query, users_ids)

                column_names = ','.join(str(column[0]) for column in orig_db_cursor.description if column[0] is not None)
                users = orig_db_cursor.fetchall()

                for user in users:
                    add_to_db_table(temp_db_conn, "users", column_names, tuple(user))

                # 9º Reverted_user_pairs table
                placeholders = ','.join('?' for _ in users_ids)
                query = f'SELECT * FROM reverted_user_pairs WHERE revertant_rev IN ({placeholders})'
                orig_db_cursor.execute(query, users_ids)

                column_names = ','.join(str(column[0]) for column in orig_db_cursor.description if column[0] is not None)
                reverted_user_pairs = orig_db_cursor.fetchall()

                if reverted_user_pairs:
                    for reverted_user_pair in reverted_user_pairs:
                        add_to_db_table(temp_db_conn, "reverted_user_pairs", column_names, tuple(reverted_user_pair))

                # 10º Mutual_reverters_activities table
                if periods:
                    placeholders = ','.join('?' for _ in periods_ids)
                    query = f'SELECT * FROM mutual_reverters_activities WHERE user IN ({placeholders})'
                    orig_db_cursor.execute(query, periods_ids)

                    column_names = ','.join(str(column[0]) for column in orig_db_cursor.description
                                            if column[0] is not None)
                    mutual_reverters_activities = orig_db_cursor.fetchall()

                    if mutual_reverters_activities:
                        for mutual_reverters_activity in mutual_reverters_activities:
                            add_to_db_table(temp_db_conn, "mutual_reverters_activities", column_names,
                                            tuple(mutual_reverters_activity))

        input("Copy successfully created (press Enter to continue) ")
        clear_n_lines(2)

    finally:
        # No matter what, we ensure cursors end up closing
        orig_db_cursor.close()
        temp_db_cursor.close()


""" Functions to save data for each table (checking safely if the entry already exists in which case it is updated) """

def save_session_data(conn: Connection) -> (int | None, bool):
    print("\n")
    print_db_table(conn, "sessions")

    session_id = None
    session_saved = False
    session_overwritten = False

    while not session_saved:
        name = input("\nPlease, write a name to save this session ")

        sessions = fetch_items_from_db(conn, "sessions", where_clause="name=?", where_values=[name])
        if sessions:
            question = "A session with this name already exists, do you want to overwrite it? "
            answer = ask_yes_or_no_question(question)

            if answer:
                timestamp = datetime.now(timezone.utc).strftime("%m/%d/%Y %H:%M:%S")
                session_id = sessions[0][0]  # rowid of first session in the list

                update_db_table(conn, "sessions", "name=?, timestamp=?",
                                [name, timestamp], session_id)
                session_overwritten = True
                session_saved = True

            clear_n_lines(1)
        else:
            session_id = add_to_db_table(conn, "sessions", "name, timestamp",
                                         (name, datetime.now(timezone.utc).strftime("%m/%d/%Y %H:%M:%S")))
            session_saved = True

    return session_id, session_overwritten


def save_article_data(conn: Connection, article: LocalPage, session_id: int) -> int:
    column_names = ("pageid, session, title, url, site, namespace, content_model, text, discussion_page_title, "
                    "discussion_page_url, discussion_page_text")
    where_clause = "pageid=? AND session=?"
    where_values = [str(article.pageid), str(session_id)]
    set_clause = ("pageid=?, session=?, title=?, url=?, site=?, namespace=?, content_model=?, text=?, "
                  "discussion_page_title=?, discussion_page_url=?, discussion_page_text=?")
    set_values = [article.pageid, session_id, article.title, article.full_url(), article.site, article.namespace,
                  article.content_model, article.text, article.discussion_page_title, article.discussion_page_url,
                  article.discussion_page_text]
    item = (article.pageid, session_id,
            article.title, article.full_url(),
            article.site, article.namespace,
            article.content_model, article.text,
            article.discussion_page_title,
            article.discussion_page_url,
            article.discussion_page_text)

    article_id = add_or_update_if_exists(conn, "articles", column_names, where_clause, where_values,
                                         set_clause, set_values, item)

    return article_id


def save_period_data(conn: Connection, articles_ids_dict: dict[int, int], article: LocalPage,
                     info: ArticleEditWarInfo) -> int:
    article_id = articles_ids_dict[article.pageid]
    start_date_str = datetime_to_iso(info.start_date)
    end_date_str = datetime_to_iso(info.end_date)

    column_names = "article, start_date, end_date"
    where_clause = "article=? AND end_date=?"
    where_values = [article_id, end_date_str]
    set_clause = "article=?, start_date=?, end_date=?"
    set_values = [article_id, start_date_str, end_date_str]
    item = (article_id, start_date_str, end_date_str)

    period_id = add_or_update_if_exists(conn, "edit_war_analysis_periods", column_names, where_clause, where_values,
                                        set_clause, set_values, item)

    return period_id


def save_edit_war_value(conn: Connection, period_id: int, date: datetime, value: int):
    date_str = datetime_to_iso(date)

    column_names = "period, date, value"
    where_clause = "period=? AND date=?"
    where_values = [period_id, date_str]
    set_clause = "period=?, date=?, value=?"
    set_values = [period_id, date_str, value]
    item = (period_id, date_str, value)

    add_or_update_if_exists(conn, "edit_war_values", column_names, where_clause, where_values,
                            set_clause, set_values, item)


def save_user_data(conn: Connection, username: str, user_info: LocalUser) -> int:
    registration_date_str = datetime_to_iso(user_info.registration_date) \
        if user_info.registration_date is not None else None

    column_names = ("username, site, is_registered, is_blocked, registration_date, edit_count, asn, asn_description, "
                    "network_address, network_name, network_country, registrants_info")
    where_clause = "username=?"
    where_values = [username]
    set_clause = ("username=?, site=?, is_registered=?, is_blocked=?, registration_date=?, edit_count=?, asn=?, "
                  "asn_description=?, network_address=?, network_name=?, network_country=?, registrants_info=?")
    is_registered_int = int(user_info.is_registered) if user_info.is_registered is not None else None
    is_blocked_int = int(user_info.is_blocked) if user_info.is_blocked is not None else None
    set_values = [username, user_info.site, is_registered_int, is_blocked_int, registration_date_str,
                  user_info.edit_count, user_info.asn, user_info.asn_description, user_info.network_address,
                  user_info.network_name, user_info.network_country, user_info.registrants_info]
    item = (username, user_info.site, is_registered_int, is_blocked_int, registration_date_str,
            user_info.edit_count, user_info.asn, user_info.asn_description, user_info.network_address,
            user_info.network_name, user_info.network_country, user_info.registrants_info)

    user_id = add_or_update_if_exists(conn, "users", column_names, where_clause, where_values, set_clause,
                                      set_values, item)

    return user_id


def save_revision_data(conn: Connection, local_rev: LocalRevision, users_ids_dict: dict[str, int],
                       article_id: int) -> int:
    user_id = users_ids_dict[local_rev.user] if local_rev.user else None
    revid = local_rev.revid
    tags_str = ", ".join(local_rev.tags)

    column_names = "revid, article, timestamp, user, text, size, tags, comment, sha1"
    where_clause = "revid=? AND article=?"
    where_values = [revid, article_id]
    set_clause = "revid=?, article=?, timestamp=?, user=?, text=?, size=?, tags=?, comment=?, sha1=?"
    set_values = [revid, article_id, local_rev.timestamp, user_id, local_rev.text, local_rev.size, tags_str,
                  local_rev.comment, local_rev.sha1]
    item = (local_rev.revid, article_id, local_rev.timestamp, user_id, local_rev.text, local_rev.size,
            tags_str, local_rev.comment, local_rev.sha1)

    rev_id = add_or_update_if_exists(conn, "revisions", column_names, where_clause, where_values, set_clause,
                                     set_values, item)

    return rev_id


def save_revert_data(conn: Connection, revertant_rev_id: int, reverted_rev_id: int) -> int:
    revertant_rev_id_str = str(revertant_rev_id)
    reverted_rev_id_str = str(reverted_rev_id)

    column_names = "revertant_rev, reverted_rev"
    where_clause = "revertant_rev=? AND reverted_rev=?"
    where_values = [revertant_rev_id_str, reverted_rev_id_str]
    set_clause = "revertant_rev=?, reverted_rev=?"
    set_values = [revertant_rev_id_str, reverted_rev_id_str]
    item = (revertant_rev_id_str, reverted_rev_id_str)

    revert_id = add_or_update_if_exists(conn, "reverts", column_names, where_clause, where_values, set_clause,
                                        set_values, item)

    return revert_id


def save_reverted_user_pair_data(conn: Connection, revertant_rev_id: int, reverted_rev_id: int, user_id: int) -> int:
    revertant_rev_id_str = str(revertant_rev_id)
    reverted_rev_id_str = str(reverted_rev_id)
    user_id_str = str(user_id)

    column_names = "revertant_rev, reverted_rev, user"
    where_clause = "revertant_rev=? AND reverted_rev=? AND user=?"
    where_values = [revertant_rev_id_str, reverted_rev_id_str, user_id_str]
    set_clause = "revertant_rev=?, reverted_rev=?, user=?"
    set_values = [revertant_rev_id_str, reverted_rev_id_str, user_id_str]
    item = (revertant_rev_id_str, reverted_rev_id_str, user_id_str)

    reverted_user_pair_id = add_or_update_if_exists(conn, "reverted_user_pairs", column_names, where_clause,
                                                    where_values, set_clause, set_values, item)

    return reverted_user_pair_id


def save_mutual_revert_data(conn: Connection, revs_ids_dict: dict[int, int],
                            revert_1: tuple[LocalRevision, LocalRevision, set[str]],
                            revert_2: tuple[LocalRevision, LocalRevision, set[str]]) -> int:
    revertant_rev_1_id_str = str(revs_ids_dict[revert_1[0].revid])
    reverted_rev_1_id_str = str(revs_ids_dict[revert_1[1].revid])
    revertant_rev_2_id_str = str(revs_ids_dict[revert_2[0].revid])
    reverted_rev_2_id_str = str(revs_ids_dict[revert_2[1].revid])

    column_names = "revertant_rev_1, reverted_rev_1, revertant_rev_2, reverted_rev_2"
    where_clause = "revertant_rev_1=? AND reverted_rev_1=? AND revertant_rev_2=? AND reverted_rev_2=?"
    where_values = [revertant_rev_1_id_str, reverted_rev_1_id_str, revertant_rev_2_id_str, reverted_rev_2_id_str]
    set_clause = "revertant_rev_1=?, reverted_rev_1=?, revertant_rev_2=?, reverted_rev_2=?"
    set_values = [revertant_rev_1_id_str, reverted_rev_1_id_str, revertant_rev_2_id_str, reverted_rev_2_id_str]
    item = (revertant_rev_1_id_str, reverted_rev_1_id_str, revertant_rev_2_id_str, reverted_rev_2_id_str)

    mutual_revert_id = add_or_update_if_exists(conn, "mutual_reverts", column_names, where_clause, where_values,
                                               set_clause, set_values, item)

    return mutual_revert_id


def save_mutual_reverters_activity(conn: Connection, user_id: int, period_id: int, n_mutual_reverts: int) -> int:
    user_id_str = str(user_id)
    period_id_str = str(period_id)
    n_mutual_reverts_str = str(n_mutual_reverts)

    column_names = "user, period, n_mutual_reverts"
    where_clause = "user=? AND period=?"
    where_values = [user_id_str, period_id_str]
    set_clause = "user=?, period=?, n_mutual_reverts=?"
    set_values = [user_id_str, period_id_str, n_mutual_reverts_str]
    item = (user_id_str, period_id_str, n_mutual_reverts_str)

    mutual_reverters_activity_id = add_or_update_if_exists(conn, "mutual_reverters_activities", column_names,
                                                           where_clause, where_values, set_clause, set_values, item)

    return mutual_reverters_activity_id

