import pywikibot


class LocalRevision(object):
    _revision: pywikibot.page._revision     # Referenced revision
    _revid: int
    _article: int
    _timestamp: str
    _user: str
    _text: str
    _size: int
    _tags: str
    _comment: str
    _sha1: str

    # Constructor to build class parameters from database
    def __init__(self, revid: int, timestamp: str, user: str, text: str, size: int, tags: str,
                 comment: str, sha1: str, revision: pywikibot.page._revision = None):
        self._revision = revision
        self._revid = revid
        self._timestamp = timestamp
        self._user = user
        self._text = text
        self._size = size
        self._tags = tags
        self._comment = comment
        self._sha1 = sha1


    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, value):
        self._size = value

    @property
    def revision(self):
        return self._revision

    @revision.setter
    def revision(self, value):
        self._revision = value

    @property
    def sha1(self):
        return self._sha1

    @sha1.setter
    def sha1(self, value):
        self._sha1 = value

    @property
    def comment(self):
        return self._comment

    @comment.setter
    def comment(self, value):
        self._comment = value

    @property
    def tags(self):
        return self._tags

    @tags.setter
    def tags(self, value):
        self._tags = value

    @property
    def user(self):
        return self._user

    @user.setter
    def user(self, value):
        self._user = value

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        self._text = value

    @property
    def revid(self):
        return self._revid

    @revid.setter
    def revid(self, value):
        self._revid = value

    @property
    def timestamp(self):
        return self._timestamp

    @timestamp.setter
    def timestamp(self, value):
        self._timestamp = value

    @property
    def article(self):
        return self._article

    @article.setter
    def article(self, value):
        self._article = value


    def __eq__(self, other):
        return self.revid == other.revid

    def __ne__(self, other):
        return self.revid != other.revid

    def __lt__(self, other):
        return self.revid < other.revid

    def __le__(self, other):
        return self.revid <= other.revid

    def __gt__(self, other):
        return self.revid > other.revid

    def __ge__(self, other):
        return self.revid >= other.revid

    def __hash__(self):
        return hash(self.revid)


    @classmethod
    def init_with_revision(cls, revision: pywikibot.page._revision):
        """ Constructor to build class parameters from pywikibot.page._revision"""

        return cls(revision.get("revid"), revision.get("timestamp"), cls.__extract_rev_user(revision),
                   revision.get("text"), revision.get("size"), revision.get("tags"), revision.get("comment"),
                   revision.get("sha1"), revision=revision)


    @staticmethod
    def __extract_rev_user(rev: pywikibot.page._revision) -> str:
        if rev.get("user") is not None:
            user = rev.get("user")
        else:
            user = "No user info available"

        return user

