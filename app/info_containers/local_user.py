from datetime import datetime


class LocalUser(object):
    _username: str
    _site: str
    _is_registered: bool
    _is_blocked: bool
    _registration_date: datetime
    _edit_count: int
    _asn: str
    _asn_description: str
    _network_address: str
    _network_name: str
    _network_country: str
    _registrants_info: str

    def __init__(self, username: str, site: str = None, is_registered: bool = None,
                 is_blocked: bool = None, registration_date: datetime = None, edit_count: int = None,
                 asn: str = None, asn_description: str = None, network_address: str = None, network_name: str = None,
                 network_country: str = None, registrants_info: str = None):

        self._username = username
        self._site = site
        self._is_registered = is_registered
        self._is_blocked = is_blocked
        self._registration_date = registration_date
        self._edit_count = edit_count
        self._asn = asn
        self._asn_description = asn_description
        self._network_address = network_address
        self._network_name = network_name
        self._network_country = network_country
        self._registrants_info = registrants_info

    @property
    def asn(self):
        return self._asn

    @asn.setter
    def asn(self, value):
        self._asn = value

    @property
    def is_blocked(self):
        return self._is_blocked

    @is_blocked.setter
    def is_blocked(self, value):
        self._is_blocked = value

    @property
    def registrants_info(self):
        return self._registrants_info

    @registrants_info.setter
    def registrants_info(self, value):
        self._registrants_info = value

    @property
    def network_name(self):
        return self._network_name

    @network_name.setter
    def network_name(self, value):
        self._network_name = value

    @property
    def is_registered(self):
        return self._is_registered

    @is_registered.setter
    def is_registered(self, value):
        self._is_registered = value

    @property
    def username(self):
        return self._username

    @username.setter
    def username(self, value):
        self._username = value

    @property
    def site(self):
        return self._site

    @site.setter
    def site(self, value):
        self.site = value

    @property
    def edit_count(self):
        return self._edit_count

    @edit_count.setter
    def edit_count(self, value):
        self._edit_count = value

    @property
    def network_country(self):
        return self._network_country

    @network_country.setter
    def network_country(self, value):
        self._network_country = value

    @property
    def asn_description(self):
        return self._asn_description

    @asn_description.setter
    def asn_description(self, value):
        self._asn_description = value

    @property
    def registration_date(self):
        return self._registration_date

    @registration_date.setter
    def registration_date(self, value):
        self._registration_date = value

    @property
    def network_address(self):
        return self._network_address

    @network_address.setter
    def network_address(self, value):
        self._network_address = value