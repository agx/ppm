#!/usr/bin/python3
# vim: set fileencoding=utf-8 :
#
# (C) 2010,2011,2020 Guido Guenther <agx@sigxcpu.org>
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
#    along with this program; if not, see <http://www.gnu.org/licenses/>.

from builtins import str
from builtins import range
from builtins import object
import locale
import logging
import os
import sys
import time

import ppm
from ppm.modemproxy import (ModemManagerProxy, ModemError)
from ppm.providerdb import ProviderDB
from ppm.accountdb import AccountDB

import gettext
import gi
from gi.repository import Gio
from gi.repository import GObject
from gi.repository import GLib
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk  # noqa: E402
from gi.repository import Gdk  # noqa: E402


_ = None


# Needs to happen early so we can use it to create classes based on templates
resource = Gio.Resource.load(os.path.join(ppm.data_dir, "ppm.gresource"))
resource._register()

# The controller receives input and initiates a response by making calls on model
# objects. A controller accepts input from the user and instructs the model and
# view to perform actions based on that input.
class PPMController(Gtk.Application):
    """
    @ivar providers: the possible providers
    @ivar imsi: the imsi if we could fetch it from the modem
    @ivar account: the account associated with the SIM card
    @ivar provider: current provider
    """

    __gsignals__ = {
        # Emitted when we got the new account balance from the provider
        'balance-info-changed': (GObject.SignalFlags.RUN_FIRST, None,
                                 [object]),
        # Emitted when the provider changed
        'provider-changed': (GObject.SignalFlags.RUN_FIRST, None,
                             [object]),
    }

    def _connect_mm_signals(self):
        self.mm.connect('request-started', self.on_mm_request_started)
        self.mm.connect('request-finished', self.on_mm_request_finished)
        self.mm.connect('got-modems', self.on_mm_got_modems)

    def __init__(self):
        Gtk.Application.__init__(self, application_id=ppm.app_id)
        self.mm = None
        self.mm_tries = 0
        self.imsi = None
        self.provider = None
        self.account = None
        self.view = None
        self.providerdb = ProviderDB()
        self.accountdb = AccountDB()

        self.connect('provider-changed', self.on_provider_changed)
        self.connect('balance-info-changed', self.on_balance_info_changed)

    def fetch_balance(self):
        """Fetch the current account balance from the  network"""
        if not self.mm.modem.enabled:
            self.view.show_modem_enable()

        if not self.provider.fetch_balance(self.mm,
                                           reply_func=self.on_balance_info_fetched,
                                           error_func=self.on_modem_error):
            self.view.show_provider_balance_info_missing(self.provider)
            logging.error("No idea how to fetch account information for "
                          "%s in %s.", self.provider.name, self.provider.country)

    def top_up_balance(self):
        code = self.view.get_top_up_code()
        if not self.provider.top_up(self.mm, code,
                                    reply_func=self.on_balance_topped_up,
                                    error_func=self.on_modem_error):
            self.view.show_provider_top_up_info_missing(self.provider)
            logging.error("No idea how to top up balance for "
                          "%s in %s.", self.provider.name, self.provider.country)

    def set_provider(self, provider=None, account=None, country_code=None,
                     name=None):
        """
        Change the current provider to provider and inform the view

        Input can be a provider, an account or (name, country_code)
        Once finished we know how to access account balance, top up, etc.
        """
        if account:
            name = account.props.name
            country_code = account.props.code

        if name and country_code:
            provider = self.providerdb.get_provider(country_code, name)

        if not provider:
            raise Exception("No valid account or provider")

        self.provider = provider
        self.emit('provider-changed', provider)

    def _imsi_to_network_id(self, imsi):
        """Extract mmc and mnc from imsi"""
        mcc = imsi[0:3]
        mnc = imsi[3:5]
        return (mcc, mnc)

    def get_provider_interactive(self, imsi=None):
        """
        Given the imsi, determine the provider based on that information
        from providerdb, request user input where ncessary

        @param imsi: If given use this to dertimine the mcc and mnc
            and from that the provider. If set to C{None} request all
            information from the user.
        @type imsi: C{str}
        """
        self.providers = []
        if imsi:
            mcc, mnc = self._imsi_to_network_id(imsi)
            self.providers = self.providerdb.get_providers(mcc, mnc)

        if len(self.providers) == 1:
            self.set_provider(self.providers[0])
        elif len(self.providers):
            # More than one provider matching mcc/mnc, let user select
            self.view.show_provider_assistant(self.providers)
        else:
            if imsi:
                self.view.show_provider_unknown(mcc, mnc)
            else:
                self.view.show_provider_assistant(None)

    def _get_account_from_accountdb(self, imsi):
        """
        Based on the imsi check if we already now all the account details
        """
        self.account = self.accountdb.fetch(imsi)
        if self.account:
            self.set_provider(account=self.account)
        return self.account

    def init_account_and_provider(self):
        """Fetch the imsi and deduce account and provider information"""

        logging.debug("Fetching account information")

        if not self.mm.modem.enabled:
            self.view.show_modem_enable()
            return False

        try:
            self.imsi = self.mm.get_imsi()
        except ModemError as me:
            logging.warning("Can't get imsi: %s", me.msg)
            if me.is_forbidden():
                self.view.show_provider_assistant()
                return False

            self.view.show_modem_error(me.msg)
            return False

        try:
            account = self._get_account_from_accountdb(self.imsi)
        except Exception:
            # Fetching account from the DB failed, so start over
            account = None

        if account:
            # Since we have the account in the db we can safely fetch the
            # provider information from the providerdb
            self.providerdb.get_provider(self.account.name,
                                         self.account.code)
        else:
            # Account not known yet, get provider interactively
            self.account = None
            self.get_provider_interactive(self.imsi)

        # Everything worked out, disable the timer.
        return False

    def on_mm_got_modems(self, obj, mm_proxy):
        if mm_proxy.modems:
            modem = mm_proxy.modems[0]  # FIXME: handle multiple modems
            logging.debug("Using modem %s" % modem)
            self.mm.set_modem(modem)
            GLib.timeout_add(500, self.init_account_and_provider)
        else:
            self.view.show_no_modem_found()

    def setup(self):
        logging.debug("Setting up")
        # Wait for MM Proxy to become ready:
        if not self.mm.ready():
            self.mm_tries += 1
            logging.debug("Not yet ready, rescheduling")
            return True
        if self.mm_tries > 5:
            self.view.show_no_modem_found()
            return False

        self.mm.dbus_find_modems()
        return False

    def schedule_setup(self):
        """Schedule another run of setup"""

        self.mm = ModemManagerProxy()
        self._connect_mm_signals()
        GLib.timeout_add(500, self.setup)

    def enable_modem(self):
        """Enable the modem"""
        self.mm.modem_enable(reply_func=self.on_modem_enable,
                             error_func=self.on_modem_error)

    def quit(self):
        """Clean up"""
        logging.debug("Quitting...")
        self.view.close()
        Gtk.main_quit()

    def get_provider_countries(self):
        return self.providerdb.get_countries()

    def get_provider_providers(self, country_code):
        return self.providerdb.get_providers_by_code(country_code)

    def get_country_by_code(self, code):
        return self.providerdb.get_country_by_code(code)

    def on_mm_request_started(self, obj, mm_proxy):
        logging.debug("Started modem request: %s", mm_proxy.request)
        self.view.show_modem_response()

    def on_mm_request_finished(self, obj, mm_proxy):
        logging.debug("Finished modem request")
        self.view.close_modem_response()

    def on_balance_info_fetched(self, var, user_data):
        """Callback for succesful MM fetch balance info call"""
        balance = var.unpack()[0]
        self.emit('balance-info-changed', balance)

    def on_balance_topped_up(self, var, user_data):
        """Callback for succesful MM topup balance call"""
        reply = var.unpack()[0]
        self.view.update_top_up_information(reply)

    def on_modem_enable(self, var, user_data):
        """Callback for succesful MM enable modem  call"""
        GLib.timeout_add(500, self.init_account_and_provider)

    def on_modem_enable_error(self, e):
        """Callback for failed MM enable modem  call"""
        self.on_modem_error(e)
        GLib.timeout_add(500, self.init_account_and_provider)

    def on_modem_error(self, e):
        logging.error(e.msg)
        self.view.show_modem_error(e.msg)
        # The modem might have disconnected. So reschedule the setup
        self.schedule_setup()

    def on_provider_changed(self, obj, provider):
        """Act on provider-changed signal"""
        logging.debug("Provider changed to '%s'", provider.name)

        self.view.update_provider_name(provider.name)
        self.view.update_topup_length(provider.top_up_code_length)

        if self.imsi and not self.account:
            # We have an imsi and the user told us what provider to use:
            self.account = self.accountdb.add(self.imsi, provider)
        elif self.account:
            # Update an existing account with the user provided information
            self.account.update_provider(provider)
            if self.account.props.timestamp:
                self.view.update_account_balance_information(
                    self.account.balance,
                    self.account.timestamp)

    def on_balance_info_changed(self, obj, balance):
        """Act on balance-info-changed signal"""
        logging.debug("Balance info changed")

        timestamp = time.asctime()
        if self.account:
            self.account.update_balance(balance, timestamp)

        self.view.update_account_balance_information(balance, timestamp)

# Views
@Gtk.Template.from_resource('/org/gnome/PrepaidManager/ui/ppm-error-dialog.ui')
class PPMErrorDialog(Gtk.Dialog):
    __gtype_name__ = "PPMErrorDialog"
    error_origin = Gtk.Template.Child()
    error_detail = Gtk.Template.Child()
    
    def __init__(self, origin, detail):
        Gtk.Dialog.__init__(self)

        self.error_origin.set_text(origin)
        self.error_detail.set_text(detail)
        self.set_title(GLib.get_application_name())
        

@Gtk.Template.from_resource('/org/gnome/PrepaidManager/ui/ppm.ui')
class PPMDialog(Gtk.ApplicationWindow):
    __gtype_name__ = "PPMDialog"

    label_balance_provider_name = Gtk.Template.Child()
    label_topup_provider_name = Gtk.Template.Child()
    label_balance_info = Gtk.Template.Child()
    label_balance_timestamp = Gtk.Template.Child()
    label_balance_from = Gtk.Template.Child()
    entry_code = Gtk.Template.Child()
    button_top_up = Gtk.Template.Child()
    label_top_up_reply = Gtk.Template.Child()
    vbox_main = Gtk.Template.Child()

    def _init_about_dialog(self):
        self.about_dialog = Gtk.AboutDialog(
            parent=self,
            authors=["Guido Günther <agx@sigxcpu.org>"],
            website="https://honk.sigxcpu.org/piki/projects/ppm/",
            website_label=_("Website"),
            comments=_("Manage balance of prepaid GSM SIM cards"),
            wrap_license=True,
            version=ppm.version,
            logo_icon_name='ppm',
            license_type=Gtk.License.GPL_3_0)

    def _init_subdialogs(self):
        """Init dialogs shown from the main window"""
        self.provider_info_missing_dialog = PPMProviderInfoMissingDialog(self)
        self.provider_assistant = PPMProviderAssistant(self)
        self._init_about_dialog()

    def _init_infobars(self):
        self.enable_modem_info_bar = PPMEnableModemInfoBar(self)
        self.modem_response_info_bar = PPMModemResponseInfoBar(self)
        self.no_modem_found_info_bar = PPMNoModemFoundInfoBar(self)

    def _setup_ui(self):
        self._init_infobars()
        self._init_subdialogs()

    def _add_actions(self):
        action = Gio.SimpleAction(name='about')
        action.set_enabled(True)
        action.connect('activate', self.on_about_activated, None)

        self.add_action(action)

    def __init__(self, controller):
        Gtk.ApplicationWindow.__init__(self)
        self.code_len = 0
        self.controller = controller
        # Register ourself to the controller
        self.controller.view = self

        self._add_actions()
        self._setup_ui()
        self.show()

    @property
    def info_bar_container(self):
        """The widget that contains the main info bar"""
        return self.vbox_main

    def get_top_up_code(self):
        return self.entry_code.get_text().strip()

    @Gtk.Template.Callback("on_balance_top_up_clicked")
    def on_balance_top_up_clicked(self, dummy):
        self.clear_top_up_information()
        self.controller.top_up_balance()

    def on_about_activated(self, *argv):
        self.about_dialog.show()

    @Gtk.Template.Callback("on_balance_info_renew_clicked")
    def on_balance_info_renew_clicked(self, dummy):
        self.controller.fetch_balance()

    @Gtk.Template.Callback("on_provider_change_clicked")
    def on_provider_change_clicked(self, dummy):
        self.controller.get_provider_interactive(imsi=None)

    @Gtk.Template.Callback("on_entry_code_insert")
    def on_entry_code_insert(self, entry):
        cur_len = entry.get_text_length()
        sensitive = True

        if self.code_len > 0:
            self.entry_code.set_progress_fraction(cur_len / self.code_len)
            if cur_len != self.code_len:
                sensitive = False
        self.button_top_up.set_sensitive(sensitive)

    def update_provider_name(self, provider_name):
        self.label_balance_provider_name.set_text(provider_name)
        self.label_topup_provider_name.set_text(provider_name)

    def update_topup_length(self, len):
        """Adjust GtkEntry to the length of the top up code"""
        placeholder = ''
        self.code_len = len
        if len:
            placeholder = "".join([str(x)[-1] for x in range(1, len + 1)])
        self.entry_code.set_placeholder_text(placeholder)

    def update_account_balance_information(self, balance_text, timestamp):
        self.label_balance_info.set_text(balance_text)
        self.label_balance_timestamp.set_text(timestamp)
        self.label_balance_timestamp.show()
        self.label_balance_from.show()

    def update_top_up_information(self, reply):
        self.label_top_up_reply.set_text(reply)

    def clear_top_up_information(self):
        self.label_top_up_reply.set_text("")

    def show_provider_balance_info_missing(self, provider):
        self.provider_info_missing_dialog.balance_info_missing(provider)

    def show_provider_top_up_info_missing(self, provider):
        self.provider_info_missing_dialog.top_up_info_missing(provider)

    def show_provider_unknown(self, mcc, mnc):
        self.provider_info_missing_dialog.provider_unknown(mcc, mnc)

    def show_modem_error(self, msg):
        logging.debug(msg)
        dialog = PPMErrorDialog(_("Modem error"), msg)
        dialog.run()
        dialog.destroy()

    def show_modem_enable(self):
        self.enable_modem_info_bar.show()

    def show_provider_assistant(self, providers=None):
        self.provider_assistant.show(providers)

    def show_no_modem_found(self):
        """Show the 'no modem found' info bar"""
        self.no_modem_found_info_bar.show()

    def show_error(self, msg):
        """show generic error"""
        logging.debug(msg)
        dialog = PPMErrorDialog(_("Error"), msg)
        dialog.run()
        dialog.destroy()

    def show_modem_response(self):
        self.modem_response_info_bar.show()

    def close_modem_response(self):
        self.modem_response_info_bar.hide()


class PPMInfoBar(object):
    def __init__(self, view):
        self.view = view
        self.controller = view.controller
        self.info_bar = Gtk.InfoBar()

    def show(self):
        self.view.info_bar_container.add(self.info_bar)
        self.info_bar.show_all()

    def hide(self):
        self.info_bar.hide()
        self.view.info_bar_container.remove(self.info_bar)
        self.view.resize(1, 1)


class PPMEnableModemInfoBar(PPMInfoBar):
    """Info bar attached to the main window"""

    def __init__(self, view):
        PPMInfoBar.__init__(self, view)
        self.info_bar.add_button(_("Enable"), Gtk.ResponseType.OK)
        self.info_bar.set_message_type(Gtk.MessageType.WARNING)
        self.msg_label = Gtk.Label(label=_("Modem not enabled"))
        content_area = self.info_bar.get_content_area()
        content_area.add(self.msg_label)
        self.msg_label.show()
        self.info_bar.connect("response", self.on_enable_clicked)

    def on_enable_clicked(self, info_bar, response_id):
        self.hide()
        self.controller.enable_modem()


class PPMModemResponseInfoBar(PPMInfoBar):
    """Info bar used when waiting for a modem response"""
    def __init__(self, view):
        PPMInfoBar.__init__(self, view)
        self.info_bar.set_message_type(Gtk.MessageType.INFO)
        self.progressbar = Gtk.ProgressBar(text=_("Awaiting modem response..."))
        self.progressbar.set_show_text(True)
        content_area = self.info_bar.get_content_area()
        content_area.add(self.progressbar)

    def show(self):
        logging.debug("Awaiting modem resonse")
        self.timer = GLib.timeout_add(50, self.do_progress,
                                      priority=GLib.PRIORITY_HIGH)
        PPMInfoBar.show(self)

    def hide(self):
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = None
        PPMInfoBar.hide(self)

    def do_progress(self):
        self.progressbar.pulse()
        return True


class PPMNoModemFoundInfoBar(PPMInfoBar):
    def __init__(self, container):
        PPMInfoBar.__init__(self, container)
        self.info_bar.set_message_type(Gtk.MessageType.WARNING)
        self.msg_label = Gtk.Label(label=_("No modem found."))
        content_area = self.info_bar.get_content_area()
        content_area.add(self.msg_label)
        self.info_bar.add_button(_("Try again"), Gtk.ResponseType.OK)
        self.info_bar.connect("response", self.on_try_again_clicked)

    def on_try_again_clicked(self, info_bar, response_id):
        logging.debug("Rescheduling modem setup")
        self.hide()
        self.controller.schedule_setup()


@Gtk.Template.from_resource('/org/gnome/PrepaidManager/ui/ppm-provider-assistant.ui')
class PPMProviderAssistant(Gtk.Assistant):
    PAGE_INTRO, PAGE_COUNTRIES, PAGE_PROVIDERS, PAGE_CONFIRM = list(range(0, 4))

    __gtype_name__ = "PPMProviderAssistant"

    vbox_countries = Gtk.Template.Child()
    treeview_countries = Gtk.Template.Child()
    vbox_providers = Gtk.Template.Child()
    treeview_providers = Gtk.Template.Child()
    liststore_providers = Gtk.Template.Child()
    label_country = Gtk.Template.Child()
    label_provider = Gtk.Template.Child()

    def __init__(self, main_dialog):
        Gtk.Assistant.__init__(self)
        self.set_transient_for(main_dialog)
        self.liststore_countries = None
        self.country_code = None
        self.provider = None
        self.possible_providers = None
        self.providers_initialized = False
        self.controller = Gio.Application.get_default()

    def _get_current_country_from_locale(self):
        (l, enc) = locale.getlocale()
        code = l.lower().split('_')[0]
        logging.debug("Assuming your in country %s" % code)
        return code

    def _select_country_row(self, iter):
        path = self.liststore_countries.get_path(iter)
        treeselection = self.treeview_countries.get_selection()
        treeselection.select_path(path)
        self.treeview_countries.scroll_to_cell(path)
        self.set_page_complete(self.vbox_countries, True)

    def _fill_liststore_countries(self):
        """Fille the countries liststore with all known countries"""
        lcode = self._get_current_country_from_locale()
        if not self.liststore_countries:
            self.liststore_countries = self.treeview_countries.get_model()
            for (country, code) in self.controller.get_provider_countries():
                if country is None:
                    country = code
                iter = self.liststore_countries.append()
                self.liststore_countries.set_value(iter, 0, country)
                self.liststore_countries.set_value(iter, 1, code)
                if code == lcode:
                    self.country_code = code
                    self._select_country_row(iter)

    def _providers_only_page_func(self, current_page, user_data):
        if current_page < self.PAGE_PROVIDERS:
            return self.PAGE_PROVIDERS
        else:
            return current_page + 1

    def _all_pages_func(self, current_page, user_data):
        return current_page + 1

    def show(self, providers=None):
        self.possible_providers = providers
        self.provider = None
        self.providers_initialized = False

        if not self.possible_providers:
            # No list of possible providers so allow to select the country first
            self._fill_liststore_countries()
            self.set_forward_page_func(self._all_pages_func, None)
        else:
            # List of possible providers given, all from the same country
            self.country_code = self.possible_providers[0].country
            self.set_forward_page_func(self._providers_only_page_func,
                                                 None)
        Gtk.Widget.show(self)

    def close(self):
        self.hide()

    @Gtk.Template.Callback("on_ppm_provider_assistant_cancel")
    def on_ppm_provider_assistant_cancel(self, obj):
        logging.debug("Assistant canceled.")
        self.close()

    def _fill_provider_liststore_by_country_code(self, country_code):
        self.liststore_providers.clear()
        for provider in self.controller.get_provider_providers(country_code):
            iter = self.liststore_providers.append()
            self.liststore_providers.set_value(iter, 0, provider)

    def _fill_provider_liststore_by_providers(self):
        self.liststore_providers.clear()
        for provider in self.possible_providers:
            iter = self.liststore_providers.append()
            self.liststore_providers.set_value(iter,
                                               0,
                                               provider.name)

    @Gtk.Template.Callback("on_ppm_provider_assistant_prepare")
    def on_ppm_provider_assistant_prepare(self, obj, page):
        if self.get_current_page() == self.PAGE_PROVIDERS:
            if self.possible_providers:
                if self.providers_initialized:
                    return
                else:
                    self.providers_initialized = True
                self._fill_provider_liststore_by_providers()
                self.providers_intialized = True
            else:
                if self.country_code == self.providers_initialized:
                    return
                else:
                    self.providers_initialized = self.country_code
                self._fill_provider_liststore_by_country_code(self.country_code)
        elif self.get_current_page() == self.PAGE_CONFIRM:
            country = self.controller.get_country_by_code(self.country_code)
            label = country if country else self.country_code
            self.label_country.set_text(label)
            self.label_provider.set_text(self.provider)

    @Gtk.Template.Callback("on_treeview_countries_changed")
    def on_treeview_countries_changed(self, obj):
        selection = self.treeview_countries.get_selection()
        (model, iter) = selection.get_selected()
        if not iter:
            return
        self.country_code = model.get_value(iter, 1)
        self.set_page_complete(self.vbox_countries, True)

    @Gtk.Template.Callback("on_treeview_providers_changed")
    def on_treeview_providers_changed(self, obj):
        selection = self.treeview_providers.get_selection()
        (model, iter) = selection.get_selected()
        if not iter:
            return
        self.provider = model.get_value(iter, 0)
        self.set_page_complete(self.vbox_providers, True)

    @Gtk.Template.Callback("on_ppm_provider_assistant_close")
    def on_ppm_provider_assistant_close(self, obj):
        logging.debug("Selected: %s  %s", self.provider, self.country_code)
        self.close()
        self.controller.set_provider(name=self.provider,
                                     country_code=self.country_code)


class PPMProviderInfoMissingDialog(object):
    """
    If information about the provider is missing redirect the user to a webpage
    that explains howto provide that information
    """

    wiki_url = ('<a href = \"http://live.gnome.org/NetworkManager/'
                'MobileBroadband/ServiceProviders\">GNOME Wiki</a>')

    def __init__(self, main_dialog):
        self.dialog = Gtk.MessageDialog(parent=main_dialog,
                                        modal=True,
                                        destroy_with_parent=True,
                                        message_type=Gtk.MessageType.INFO,
                                        buttons=Gtk.ButtonsType.OK)
        self.messages = {
            'balance_info_missing':
            _("We can't find the information on how to query the "
              "account balance from your provider '%s' in our database."),
            'top_up_info_missing':
            _("We can't find the information on how to top up the "
              "balance for your provider '%s' in our database."),
            'provider_unknown':
            _("We can't find any information about your provider with "
              "mcc '%s' and mnc '%s'.")
        }
        self.common_msg = _("\n\nYou can go to %s to learn how to provide that "
                            "information.")

    def _run(self, msg):
        msg += self.common_msg % self.wiki_url
        self.dialog.set_markup(msg)
        self.dialog.run()
        self.dialog.hide()

    def balance_info_missing(self, provider):
        msg = self.messages['balance_info_missing'] % provider.name
        self._run(msg)

    def top_up_info_missing(self, provider):
        msg = self.messages['top_up_info_missing'] % provider.name
        self._run(msg)

    def provider_unknown(self, mcc, mnc):
        msg = self.messages['provider_unknown'] % (mcc, mnc)
        self._run(msg)


def setup_i18n():
    global _
    locale.setlocale(locale.LC_ALL, '')
    gettext.install(ppm.gettext_app, ppm.gettext_dir)
    gettext.bindtextdomain(ppm.gettext_app, ppm.gettext_dir)
    locale.bindtextdomain(ppm.gettext_app, ppm.gettext_dir)
    _ = gettext.gettext
    logging.debug('Using locale: %s', locale.getlocale())


def setup_prgname():
    """Set the prgname since gnome-shell is application based"""
    GLib.set_prgname(ppm.app_id)
    Gdk.set_program_class(ppm.app_id)
    GLib.set_application_name(_("Prepaid Manager"))


def main(args):
    parser = GLib.option.OptionParser()
    parser.add_option("--debug", "-d", action="store_true", dest="debug",
                      help="enable debugging", default=False)
    options, args = parser.parse_args()

    if options.debug:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    logging.basicConfig(level=log_level,
                        format='ppm: %(levelname)s: %(message)s')
    logging.debug("%s %s", ppm.app_id, ppm.version)

    setup_i18n()
    setup_prgname()

    controller = PPMController()
    PPMDialog(controller)
    controller.schedule_setup()

    Gtk.main()


if __name__ == "__main__":
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        logging.debug("Received KeyboardInterrupt. Exiting application.")
    except SystemExit:
        raise
