from typing import Iterable

import pywikibot


class LocalPage(object):
    _page: pywikibot.Page       # Referenced article
    _pageid: int
    _title: str
    _site: str
    _namespace: str
    _url: str
    _content_model: str
    _text: str
    _discussion_page_title: str
    _discussion_page_url: str
    _discussion_page_text: str

    # Constructor to build class parameters from database
    def __init__(self, pageid: int, title: str, site: str, namespace: str, url: str, content_model: str,
                 discussion_page_title: str, discussion_page_url: str, text: str = None,
                 discussion_page_text: str = None, page: pywikibot.Page = None):
        self._page = page
        self._pageid = pageid
        self._title = title
        self._site = site
        self._namespace = namespace
        self._url = url
        self._content_model = content_model
        self._text = text
        self._discussion_page_title = discussion_page_title
        self._discussion_page_url = discussion_page_url
        self._discussion_page_text = discussion_page_text


    @property
    def page(self):
        if self._page is None:
            fam, code = self._site.split(":")
            self._page = pywikibot.Page(pywikibot.Site(code, fam), self._title)

        return self._page

    @page.setter
    def page(self, value):
        self._page = value

    @property
    def content_model(self):
        return self._content_model

    @content_model.setter
    def content_model(self, value):
        self._content_model = value

    @property
    def discussion_page_title(self):
        return self._discussion_page_title

    @discussion_page_title.setter
    def discussion_page_title(self, value):
        self._discussion_page_title = value

    @property
    def discussion_page_url(self):
        return self._discussion_page_url

    @discussion_page_url.setter
    def discussion_page_url(self, value):
        self._discussion_page_url = value

    @property
    def discussion_page_text(self):
        return self._discussion_page_text

    @discussion_page_text.setter
    def discussion_page_text(self, value):
        self._discussion_page_text = value

    @property
    def site(self):
        return self._site

    @site.setter
    def site(self, value):
        self._site = value

    @property
    def namespace(self):
        return self._namespace

    @namespace.setter
    def namespace(self, value):
        self._namespace = value

    @property
    def title(self):
        if self._title is None:
            title = self._page.title()
        else:
            title = self._title

        return title

    @title.setter
    def title(self, value):
        self._title = value

    @property
    def url(self):
        return self._url

    @url.setter
    def url(self, value):
        self._url = value

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        self._text = value

    @property
    def pageid(self):
        return self._pageid

    @pageid.setter
    def pageid(self, value):
        self._pageid = value

    def __eq__(self, other):
        return self.pageid == other.pageid

    def __ne__(self, other):
        return self.pageid != other.pageid

    def __lt__(self, other):
        return self.pageid < other.pageid

    def __le__(self, other):
        return self.pageid <= other.pageid

    def __gt__(self, other):
        return self.pageid > other.pageid

    def __ge__(self, other):
        return self.pageid >= other.pageid

    def __hash__(self):
        return hash(self.pageid)


    @classmethod
    def init_with_page(cls, page: pywikibot.Page):
        """ Constructor to build class parameters from pywikibot.Page """
        discussion_page = page.toggleTalkPage()

        return cls(page.pageid, page.title(), str(page.site), page.namespace().id, page.full_url(), page.content_model,
                   discussion_page.title(), discussion_page.full_url(), page=page, text=None, discussion_page_text=None)


    def full_url(self):
        if self.url is None:
            full_url = self.page.full_url()
        else:
            full_url = self.url

        return full_url


    def categories(self, with_sort_key: bool = False, total: int = None, content: bool = False) \
            -> Iterable[pywikibot.Page]:
        categories = []

        if self.page is not None:
            categories = self.page.categories(with_sort_key, total, content)

        return categories



