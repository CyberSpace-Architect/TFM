from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.info_containers.article_edit_war_info import ArticleEditWarInfo
from app.info_containers.local_page import LocalPage
from app.info_containers.local_user import LocalUser


class Singleton:
    _instance = None       # Unique instance (class variable)
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)  # Init unique instance
        return cls._instance

    def __init__(self):
        if not self.__class__._initialized:
            # Shared dictionary for multi-purposes (right now only counting printed lines to remove)
            self._shared_dict = {}

            # Dictionary of articles with associated info (typing without from article_edit_war_info import ArticleEditWarInfo to
            # avoid circular imports)
            self._articles_with_edit_war_info_dict: dict[LocalPage, 'ArticleEditWarInfo'] = {}

            # Dictionary of users with associated info
            self._users_info_dict: dict[str, LocalUser] = {}

            self.__class__._initialized = True


    @property
    def shared_dict(self):
        return self._shared_dict

    @shared_dict.setter
    def shared_dict(self, value):
        self._shared_dict = value

    @property
    def articles_with_edit_war_info_dict(self):
        return self._articles_with_edit_war_info_dict

    @articles_with_edit_war_info_dict.setter
    def articles_with_edit_war_info_dict(self, value):
        self._articles_with_edit_war_info_dict = value

    @property
    def users_info_dict(self):
        return self._users_info_dict

    @users_info_dict.setter
    def users_info_dict(self, value):
        self._users_info_dict = value