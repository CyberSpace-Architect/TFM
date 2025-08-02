import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from sqlite3 import Connection

from utils import clear_terminal, clear_n_lines, datetime_to_iso

create_table_sql_dict: dict[str, str] = {
    "sessions" : """CREATE TABLE IF NOT EXISTS sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        timestamp TEXT NOT NULL
                    );
    """,
    "users" : """CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
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
    """
}


@contextmanager
def sqlite_connection(db: str):
    conn = sqlite3.connect(db)
    try:
        yield conn
    finally:
        conn.close()


def init_db_old(conn: Connection):
    db_already_created = True
    print("Checking db status...")

    for table, sql_statement in create_table_sql_dict.items():
        if create_table_if_not_exists(conn, table, sql_statement):
            db_already_created = False

    if db_already_created:
        input("Database already exists, press Enter to continue ")
    else:
        input("Database created, press Enter to continue ")


def init_db(conn: Connection):
    clear_terminal()
    print("\n##########################################################################################\n")
    print("Mounting database...\n")

    # Activate foreign keys as they are disabled by default
    conn.execute("PRAGMA foreign_keys = ON")

    for table, sql_statement in create_table_sql_dict.items():
        create_table_if_not_exists(conn, table, sql_statement)

    input("\nDatabase mounted, press Enter to continue ")


def reset_db(conn: Connection):
    # Create cursor to the db using the provided connection
    cursor = conn.cursor()

    try:
        print("\nDeleting previous database...")

        # Drop each table
        for table in reversed(create_table_sql_dict.keys()):
            cursor.execute(f"DROP TABLE {table};")
            print(f"\tTable '{table}' deleted")

        print("\nRecreating database...")
        for table, sql_statement in create_table_sql_dict.items():
            create_table_if_not_exists(conn, table, sql_statement)

        input("\nDatabase reset, press Enter to continue ")

        conn.commit()
    finally:
        # No matter what, we ensure cursor end up closing
        cursor.close()


def create_table_if_not_exists(conn: Connection, table: str, create_table_sql_statement: str, show_info: bool = True) -> bool | None:
    created = False

    # Create cursor to the db using the provided connection
    cursor = conn.cursor()

    try:
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

    return created


def add_to_db_table(conn: Connection, table: str, column_names: str, item: tuple, return_id:bool = False) -> bool | None:
    # Create cursor to the db using the provided connection
    cursor = conn.cursor()

    try:
        # Create a safe SQL sentence (using placeholders for values) and execute it
        placeholders = ", ".join(["?"] * len(item))
        cursor.execute(f"INSERT INTO {table} ({column_names}) VALUES ({placeholders});", item)


        # Commit changes
        conn.commit()

        if return_id:
            return cursor.lastrowid
    finally:
        # No matter what, we ensure cursor end up closing
        cursor.close()


def fetch_items_from_db(conn: Connection, table: str, where_clause: str = '?=?', where_values: list[str] = ['1','1'],
                        in_clause:bool = False, additional_where_clauses:list[str] = None,
                        additional_where_values:list[list[str]] = None) -> list | None:
    # Create cursor to the db using the provided connection
    if where_values is None:
        where_values = ['1', '1']
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

                if additional_where_clauses:
                    for i, additional_where_clause in enumerate(additional_where_clauses):
                        placeholders = ", ".join(["?"] * len(additional_where_values[i]))
                        where_clause += additional_where_clause + placeholders + ")"
                        where_values.extend(additional_where_values[i])

            # By default, where_clause is 1=1 to retrieve all contents
            cursor.execute(f"SELECT rowid,* FROM {table} WHERE {where_clause};", where_values)

            # Fetch filtered items
            items = cursor.fetchall()

            # Commit changes
            conn.commit()

        return items
    finally:
        # No matter what, we ensure cursor end up closing
        cursor.close()



def print_db_table(conn: Connection, table: str) -> list | None:
    # Create cursor to the db using the provided connection
    cursor = conn.cursor()

    try:
        cursor.execute(f"SELECT * FROM {table};")
        # Print formated column names
        column_names = [description[0] for description in cursor.description]
        columns_line = ""
        separation_line = ""
        for column in column_names:
            columns_line += column.ljust(24)
            separation_line += "----------------------- "

        half_header = "=" * (int((len(columns_line) - len(f" {table.upper()} ")) / 2))
        header_line = half_header + f" {table.upper()} " + half_header
        print("\n" + header_line + "\n\n" + columns_line + "\n" + separation_line)

        # Print table contents
        rows = cursor.fetchall()
        for row in rows:
            for value in row:
                print(str(value).ljust(24), end="")
            print("")

        # Commit changes
        conn.commit()

        return rows
    finally:
        # No matter what, we ensure cursor end up closing
        cursor.close()


def update_db_table(conn: Connection, table: str, set_clause: str, set_values, rowid: str) -> None:
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


def delete_from_db_table(conn: Connection, table: str, rowid: int) -> None:
    # Create cursor to the db using the provided connection
    cursor = conn.cursor()

    try:
        # Create a safe SQL sentence (using a placeholder for rowid) and execute it
        cursor.execute(f"DELETE FROM {table} WHERE rowid = (?);", (str(rowid),))

        # Delete autoincremental ids if the table becomes empty
        n_rows = cursor.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]

        if n_rows == 0:
            cursor.execute("DELETE FROM sqlite_sequence WHERE name = (?);", (table,))

            # If the last session is deleted, we delete contents from user table too (no cascade restriction, so it
            # has to be manually deleted)
            if table == "sessions":
                cursor.execute(f"DELETE FROM users;")
                cursor.execute(f"DELETE FROM sqlite_sequence WHERE name = (?);", ("users",))

        # Commit changes
        conn.commit()
    finally:
        # No matter what, we ensure cursor end up closing
        cursor.close()


def add_or_update_if_exists(conn: Connection, table: str, column_names: str, where_clause:str, where_values: list[str],
                            set_clause: str, set_values: list[str], item:tuple) -> int:

    stored = fetch_items_from_db(conn, table, where_clause=where_clause, where_values=where_values)

    if stored:
        rowid = stored[0][0]  # rowid
        update_db_table(conn, table, set_clause, set_values, rowid)
    else:
        rowid = add_to_db_table(conn, table, column_names, item, return_id=True)

    return rowid


""" Functions to save data for each table (checking safely if the entry already exists in which case it is updated) """

def save_session_data(conn: Connection) -> int | None:
    print_db_table(conn, "sessions")

    session_id = None
    session_saved = False

    while not session_saved:
        name = input("\nPlease, write a name to save this session ")

        session = fetch_items_from_db(conn, "sessions", where_clause="name=?", where_values=[name])
        if session:
            want_to_overwrite = re.sub(r'\s+', '', input("A session with this name already exists, "
                                                         "do you wish to overwrite it? ").lower())

            while want_to_overwrite not in {"y", "yes", "n", "no"}:
                want_to_overwrite = re.sub(r'\s+', '', input("Invalid response, please write y or yes if "
                                                             "you want to overwrite it, n or no otherwise ").lower())
                clear_n_lines(1)

            if want_to_overwrite in {"y", "yes"}:
                timestamp = datetime.now(timezone.utc).strftime("%m/%d/%Y %H:%M:%S")
                session_id = session[0]  # rowid

                update_db_table(conn, "sessions", f'name={name}, timestamp={timestamp}', session_id)
                session_saved = True

            clear_n_lines(1)
        else:
            session_id = add_to_db_table(conn, "sessions", "name, timestamp",
                                         (name, datetime.now(timezone.utc).strftime("%m/%d/%Y %H:%M:%S")),
                                         return_id=True)
            session_saved = True

    return session_id


def save_article_data(conn: Connection, article, session_id) -> int:
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


def save_period_data(conn: Connection, articles_ids_dict, article, info) -> int:
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


def save_edit_war_value(conn: Connection, period_id, date, value):
    date_str = datetime_to_iso(date)

    column_names = "period, date, value"
    where_clause = "period=? AND date=?"
    where_values = [period_id, date_str]
    set_clause = "period=?, date=?, value=?"
    set_values = [period_id, date_str, value]
    item = (period_id, date_str, value)

    add_or_update_if_exists(conn, "edit_war_values", column_names, where_clause, where_values,
                            set_clause, set_values, item)


def save_user_data(conn: Connection, username, user_info) -> int:
    registration_date_str = datetime_to_iso(user_info.registration_date) \
        if user_info.registration_date is not None else None

    column_names = ("username, is_registered, is_blocked, registration_date, edit_count, asn, asn_description, "
                    "network_address, network_name, network_country, registrants_info")
    where_clause = "username=?"
    where_values = [username]
    set_clause = ("username=?, is_registered=?, is_blocked=?, registration_date=?, edit_count=?, asn=?, "
                  "asn_description=?, network_address=?, network_name=?, network_country=?, registrants_info=?")
    is_registered_int = int(user_info.is_registered) if user_info.is_registered else None
    is_blocked_int = int(user_info.is_blocked) if user_info.is_blocked else None
    set_values = [username, is_registered_int, is_blocked_int, registration_date_str,
                  user_info.edit_count, user_info.asn, user_info.asn_description, user_info.network_address,
                  user_info.network_name, user_info.network_country, user_info.registrants_info]
    item = (user_info.username, is_registered_int, is_blocked_int, registration_date_str,
            user_info.edit_count, user_info.asn, user_info.asn_description, user_info.network_address,
            user_info.network_name, user_info.network_country, user_info.registrants_info)

    user_id = add_or_update_if_exists(conn, "users", column_names, where_clause, where_values, set_clause,
                                      set_values, item)

    return user_id


def save_revision_data(conn: Connection, local_rev, users_ids_dict, article_id):
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


def save_revert_data(conn: Connection, revertant_rev_id, reverted_rev_id):
    column_names = "revertant_rev, reverted_rev"
    where_clause = "revertant_rev=? AND reverted_rev=?"
    where_values = [revertant_rev_id, reverted_rev_id]
    set_clause = "revertant_rev=?, reverted_rev=?"
    set_values = [revertant_rev_id, reverted_rev_id]
    item = (revertant_rev_id, reverted_rev_id)

    revert_id = add_or_update_if_exists(conn, "reverts", column_names, where_clause, where_values, set_clause,
                                        set_values, item)

    return revert_id


def save_reverted_user_pair_data(conn: Connection, revertant_rev_id, reverted_rev_id, user_id):
    column_names = "revertant_rev, reverted_rev, user"
    where_clause = "revertant_rev=? AND reverted_rev=? AND user=?"
    where_values = [revertant_rev_id, reverted_rev_id, user_id]
    set_clause = "revertant_rev=?, reverted_rev=?, user=?"
    set_values = [revertant_rev_id, reverted_rev_id, user_id]
    item = (revertant_rev_id, reverted_rev_id, user_id)

    reverted_user_pair_id = add_or_update_if_exists(conn, "reverted_user_pairs", column_names, where_clause,
                                                    where_values, set_clause, set_values, item)

    return reverted_user_pair_id


def save_mutual_revert_data(conn: Connection, revs_ids_dict, revert_1, revert_2):
    revertant_rev_1_id = revs_ids_dict[revert_1[0].revid]
    reverted_rev_1_id = revs_ids_dict[revert_1[1].revid]
    revertant_rev_2_id = revs_ids_dict[revert_2[0].revid]
    reverted_rev_2_id = revs_ids_dict[revert_2[1].revid]

    column_names = "revertant_rev_1, reverted_rev_1, revertant_rev_2, reverted_rev_2"
    where_clause = "revertant_rev_1=? AND reverted_rev_1=? AND revertant_rev_2=? AND reverted_rev_2=?"
    where_values = [revertant_rev_1_id, reverted_rev_1_id, revertant_rev_2_id, reverted_rev_2_id]
    set_clause = "revertant_rev_1=?, reverted_rev_1=?, revertant_rev_2=?, reverted_rev_2=?"
    set_values = [revertant_rev_1_id, reverted_rev_1_id, revertant_rev_2_id, reverted_rev_2_id]
    item = (revertant_rev_1_id, reverted_rev_1_id, revertant_rev_2_id, reverted_rev_2_id)

    mutual_revert_id = add_or_update_if_exists(conn, "mutual_reverts", column_names, where_clause, where_values,
                                               set_clause, set_values, item)

    return mutual_revert_id


def save_mutual_reverters_activity(conn: Connection, user_id, period_id, n_mutual_reverts):
    column_names = "user, period, n_mutual_reverts"
    where_clause = "user=? AND period=?"
    where_values = [user_id, period_id]
    set_clause = "user=?, period=?, n_mutual_reverts=?"
    set_values = [user_id, period_id, n_mutual_reverts]
    item = (user_id, period_id, n_mutual_reverts)

    mutual_reverters_activity_id = add_or_update_if_exists(conn, "mutual_reverters_activities", column_names,
                                                           where_clause, where_values, set_clause, set_values, item)

    return mutual_reverters_activity_id

