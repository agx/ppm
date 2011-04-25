# vim: set fileencoding=utf-8 :
#
# (C) 2010 Guido Guenther <agx@sigxcpu.org>
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
#

import logging

class ProviderError(Exception):
    def __init__(self, msg):
        self.msg = msg


class Provider(object):
    """
    Keeps the information on howto interact with a certain provider, that
    his howto top up the ballance and how to query the current ballance

    It doesn't keep any current balance information or similar since this is
    associated with an account (a user can have several SIM cards form the same
    provider)
    """

    def __init__(self, country, name):
        self.country = country
        self.name = name
        self.fetch_balance_cmds = {}
        self.top_up_cmds = {}
        logging.debug("New provider: %s, %s", country, name)

    def add_fetch_balance_cmd(self, cmd):
        self.fetch_balance_cmds.update(cmd)
        logging.debug("Adding balance check %s" % cmd)

    def add_top_up_cmd(self, cmd):
        self.top_up_cmds.update(cmd)
        logging.debug("Adding top up %s" % cmd)

    def has_fetch_balance_cmd(self):
        # Only USSD for now
        if self.fetch_balance_cmds.has_key('ussd'):
            return True
        else:
            return False

    def has_top_up_cmd(self):
        # Only USSD for now
        if self.top_up_cmds.has_key('ussd'):
            return True
        else:
            return False

    def fetch_balance(self, mm, reply_func=None, error_func=None):
        if self.has_fetch_balance_cmd():
            mm.ussd_initiate (self.fetch_balance_cmds['ussd'],
                              reply_func=reply_func,
                              error_func=error_func)
            return True
        else:
            return False

    def top_up(self, mm, code, reply_func=None, error_func=None):
        if self.has_top_up_cmd():
            cmd = self.top_up_cmds['ussd'][0].replace(
                                                  self.top_up_cmds['ussd'][1],
                                                  code)
            logging.debug("Top up cmd: %s", cmd)
            mm.ussd_initiate (cmd, reply_func=reply_func, error_func=error_func)
            return True
        else:
            return False
