# vim: set fileencoding=utf-8 :
#
# (C) 2011 Guido Günther <agx@sigxcpu.org>
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from gi.repository import Gio
from gi.repository import GObject
import logging

from provider import Provider

class Account(GObject.GObject):
    identifier = GObject.property(type=str,
                                  nick='account identifier',
                                  blurb='the identifier of this account, usually the imsi')
    name = GObject.property(type=str,
                            nick='provider name',
                            blurb='name of the provider')
    code = GObject.property(type=str,
                            nick='country name',
                            blurb='counry code the  provider is in')
    balance = GObject.property(type=str,
                               nick='current balance',
                               blurb='current balance of this account')
    timestamp = GObject.property(type=str,
                                 nick='update timestamp',
                                 blurb='last time the balance info got updated')

    def update_provider(self, provider):
        """Update the provider information"""
        if provider.country != self.props.code:
            self.props.code = provider.country
        if provider.name != self.props.name:
            self.props.name = provider.name

    def update_balance(self, balance, timestamp):
        """Update balance information"""
        if timestamp != self.props.timestamp:
            self.props.balance = balance
            self.props.timestamp = timestamp

GObject.type_register(Account)


class AccountDB(object):
    """
    In Gsettings we keep the detailed provider information that's associated
    with an account identified by the SIM card. A user can have several
    accounts at the same provider.
    """

    PPM_GSETTINGS_ID = 'org.gnome.PrepaidManager'
    PPM_GSETTINGS_ACCOUNT_ID = PPM_GSETTINGS_ID + '.account'

    def __init__(self):
        self.settings = Gio.Settings(self.PPM_GSETTINGS_ID)
        self.accounts_path_prefix = self.settings.get_property("path") + 'accounts/'

    def is_known_account(self, imsi):
        """Do we know about this account in GSettings?"""
        return self.imsi_to_identifier(imsi) in self.settings.get_strv('accounts')

    def _account_path(self, imsi):
        """
        This key identifies the provider setup for a specific SIM card in
        GSettings. Since we might not be allowed to get the imsi from the
        phone other keys must be possible later
        """
        return '%s%s/' % (self.accounts_path_prefix,
                         self.imsi_to_identifier(imsi))

    @classmethod
    def imsi_to_identifier(klass, imsi):
        """Turn an imsi into an identifier, this allows us to support non
        imsi based accounts later"""
        return 'imsi:%s' % imsi

    def _bind_account(self, imsi):
        """Bind a new account object to a gsettings path"""

        path = self._account_path(imsi)
        account = Account()
        account.props.identifier =  self.imsi_to_identifier(imsi)
        gsettings_account = Gio.Settings(self.PPM_GSETTINGS_ACCOUNT_ID, path)
        gsettings_account.bind('provider', account, 'name',
                                Gio.SettingsBindFlags.DEFAULT)
        gsettings_account.bind('country', account, 'code',
                                Gio.SettingsBindFlags.DEFAULT)
        gsettings_account.bind('balance', account, 'balance',
                                Gio.SettingsBindFlags.DEFAULT)
        gsettings_account.bind('timestamp', account, 'timestamp',
                                Gio.SettingsBindFlags.DEFAULT)
        return account

    def fetch(self, imsi):
        """Given an imsi check if we know about it"""

        if self.is_known_account(imsi):
            logging.debug("IMSI '%s' not known", imsi)
            return None
        else:
            logging.debug("Fetching account information from '%s'",
                          self._account_path(imsi))

        account = self._bind_account(imsi)
        if account.props.name and account.props.code:
            logging.debug("Provider '%s' in '%s'", account.props.name,
                          account.props.code)
            return account
        else:
            logging.debug("Account not yet known.")
            return None

    def add(self, imsi, provider):
        """Given an imsi and a provider persist a new account with  that
        information"""
        path = self._account_path(imsi)

        logging.debug("Persisting '%s' in '%s' at '%s'",
                      provider.name,
                      provider.country,
                      path)
        account = self._bind_account(imsi)
        account.props.name = provider.name
        account.props.code = provider.country


