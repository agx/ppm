#!/usr/bin/python
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


import dbus
import dbus.mainloop.glib
import gettext
import gobject
import glib
import gtk
import locale
import logging
import os
import time

import ppm
from ppm.modemproxy import (ModemManagerProxy, ModemError)
from ppm.provider import Provider
from ppm.providerdb import ProviderDB

# The controller receives input and initiates a response by making calls on model
# objects. A controller accepts input from the user and instructs the model and
# view to perform actions based on that input.
class PPMController(gobject.GObject):
    """
    @ivar providers: the possible providers
    @ivar provider: current provider
    """

    __gsignals__ = {
        # Emitted when we got the new account balance from the provider
        'balance-info-fetched': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                                 [object]),
        }

    def _connect_mm_signals(self):
        self.mm.connect('request-started', self.on_mm_request_started)
        self.mm.connect('request-finished', self.on_mm_request_finished)

    def __init__(self):
        self.__gobject_init__()
        self.mm = None
        self.provider = None
        self.view = None
        self.providerdb = ProviderDB()

    def get_account_balance(self):
        return provider.balance

    def fetch_balance_info(self):
        """Fetch the current account balance from the  network"""
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

    def set_provider(self, provider=None, country_code=None, name=None):
        """Change the current provider to provider and inform the view"""
        if name and country_code:
            provider = self.providerdb.get_provider(country_code, name)

        if not provider:
            raise Exception("No valid provider")
        
        self.provider = provider
        self.view.update_provider_name(provider.name)
        # FIXME: fetch last stored balance from db

    def _get_provider_from_mcc_mnc(self):
        mcc, mnc = self.mm.get_network_id()
        self.providers = self.providerdb.get_providers(mcc, mnc)
        if self.providers:
            if len(self.providers) > 1:
                # More than one provider matching mcc/mnc, let user select
                self.view.show_provider_assistant(self.providers)
            else:
                self.set_provider(self.providers[0])
        else:
            self.view.show_provider_unknown(mcc, mnc)

    def init_current_provider(self):
        try:
            self._get_provider_from_mcc_mnc()
        except ModemError as me:
            logging.warning("Can't get network id: %s", me.msg)
            if me.is_forbidden():
                # FIXME: fetch last provider from GSettings       
                self.view.show_provider_assistant()
                return False
            if not me.is_disabled():
                self.view.show_modem_error(me.msg)
                return False
            logging.info("modem not enabled")
            if self.view.show_modem_enable() != gtk.RESPONSE_YES:
                return False
            else:
                self.mm.modem_enable(reply_func=self.init_current_provider)
            return True

    def setup(self):
        logging.debug("Setting up")        

        self.mm = ModemManagerProxy()
        self._connect_mm_signals()
        
        modems = self.mm.get_modems()
        if modems:
            modem = modems[0] # FIXME: handle multiple modems
            logging.debug("Using modem %s" % modem)
            self.mm.set_modem(modem)
            glib.timeout_add(500, self.init_current_provider)
        else:        
            self.view.show_error("No modem found.")
            self.quit()
        return False

    def quit(self):
        """Clean up"""
        logging.debug("Quitting...")
        self.view.close()
        gtk.main_quit()

    def get_provider_countries(self):
        return self.providerdb.get_countries()

    def get_provider_providers(self, country_code):
        return self.providerdb.get_providers_by_code(country_code)

    def on_mm_request_started(self, obj, mm_proxy):
        logging.debug("Started modem request: %s", mm_proxy.request)
        self.view.show_modem_response()

    def on_mm_request_finished(self, obj, mm_proxy):
        logging.debug("Finished modem request")
        self.view.close_modem_response()
    
    def on_balance_info_fetched(self, balance, *args):
        self.provider.balance = balance
        self.emit('balance-info-fetched', self.provider.balance)
        self.view.update_account_balance_information(self.provider.balance,
                                                     time.asctime())

    def on_balance_topped_up(self, reply):
        self.view.update_top_up_information(reply)

    def on_modem_error(self, e):
        self.view.show_modem_error(e.msg)
        logging.error(e.msg)
    
gobject.type_register(PPMController)


class PPMObject(object):
    """Dialog or window constructed via a GtkBuilder"""
    def __init__(self, view, ui):
        if view:
            self.controller = view.controller
        else:
            self.controller = None
        self._load_ui(ui)

    def _load_ui(self, ui):
        """Load the user interfade description"""
        self.builder = gtk.Builder()
        self.builder.set_translation_domain(ppm.gettext_app)
        self.builder.add_from_file(os.path.join(ppm.ui_dir, '%s.ui' % ui))
        self.builder.connect_signals(self)

    def _add_elem(self, name):
        self.__dict__[name] = self.builder.get_object(name)

    def _add_elements(self, *args):
        for name in args:
            self._add_elem(name)
    
# View
class PPMDialog(gobject.GObject, PPMObject):
    
    def _init_subdialogs(self):
        self.provider_info_missing_dialog = PPMProviderInfoMissingDialog(self)
        self.provider_assistant = PPMProviderAssistant(self)
        self.modem_response = PPMModemResponse(self)

    def _setup_ui(self):
        self.dialog = self.builder.get_object("ppm_dialog")
        self._add_elements("label_balance_provider_name",
                           "label_topup_provider_name",
                           "label_balance_info",
                           "label_balance_timestamp",
                           "label_balance_from",
                           "entry_code",
                           "button_top_up",
                           "label_top_up_reply")
        self._init_subdialogs()

    def __init__(self, controller):
        self.__gobject_init__()
        PPMObject.__init__(self, None, "ppm")
        self.controller = controller
        # Register ourself to the controller
        self.controller.view = self

        self._setup_ui()
        self.dialog.show()

    def close(self):
        self.dialog.hide()
        self.dialog.destroy()

    def get_top_up_code(self):
        return self.entry_code.get_text().strip()

    def on_close_clicked(self, dummy):
        self.controller.quit()

    def on_balance_top_up_clicked(self, dummy):
        self.clear_top_up_information()
        self.controller.top_up_balance()

    def on_balance_info_renew_clicked(self, dummy):
        self.controller.fetch_balance_info()

    def on_provider_change_clicked(self, dummy):
        # FIXME: allow to select provider
        # and communicate the change to the controller
        raise NotImplementedError

    def on_entry_code_insert(self, *args):
        if self.entry_code.get_text():
            self.button_top_up.set_sensitive(True)
        else:
            self.button_top_up.set_sensitive(False)        

    def update_provider_name(self, provider_name):
        self.label_balance_provider_name.set_text(provider_name)
        self.label_topup_provider_name.set_text(provider_name)

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
        dialog = gtk.MessageDialog(parent=self.dialog,
                                   flags=gtk.DIALOG_MODAL |
                                         gtk.DIALOG_DESTROY_WITH_PARENT,
                                   type=gtk.MESSAGE_ERROR,
                                   buttons=gtk.BUTTONS_OK)
        dialog.set_markup("Modem error: %s" % msg)
        dialog.run()
        dialog.hide()

    def show_modem_enable(self):
        """Show dialog that asks if we should enable the modem"""
        dialog = gtk.MessageDialog(parent=self.dialog,
                                   flags=gtk.DIALOG_MODAL |
                                         gtk.DIALOG_DESTROY_WITH_PARENT,
                                   type=gtk.MESSAGE_QUESTION,
                                   buttons=gtk.BUTTONS_YES_NO)
        dialog.set_markup(_("Enable Modem?"))
        ret = dialog.run()
        dialog.hide()
        return ret

    def show_provider_assistant(self, providers=None):
        self.provider_assistant.show(providers)

    def show_error(self, msg):
        """show generic error"""
        logging.debug(msg)
        error = gtk.MessageDialog(parent=self.dialog,
                                  flags=gtk.DIALOG_MODAL |
                                        gtk.DIALOG_DESTROY_WITH_PARENT,
                                  type=gtk.MESSAGE_ERROR,
                                  buttons=gtk.BUTTONS_OK)
        error.set_markup(msg)
        error.run()
        error.hide()

    def show_modem_response(self):
        self.modem_response.show()

    def close_modem_response(self):
        self.modem_response.close()


gobject.type_register(PPMDialog)

class PPMProviderAssistant(PPMObject):

    PAGE_INTRO, PAGE_COUNTRIES, PAGE_PROVIDERS, PAGE_CONFIRM = range(0, 4)
    
    def __init__(self, main_dialog):
        PPMObject.__init__(self, main_dialog, "ppm-provider-assistant")
        self.assistant = self.builder.get_object("ppm_provider_assistant")
        self._add_elements("vbox_countries",
                           "treeview_countries",
                           "vbox_providers",
                           "treeview_providers",
                           "liststore_providers",
                           "label_country",
                           "label_provider")
        self.assistant.set_transient_for(main_dialog.dialog)
        self.liststore_countries = None
        self.country_code = None
        self.provider = None
        self.possible_providers = None

    def _get_current_country_from_locale(self):
        (l, enc) = locale.getlocale()
        code = l.lower().split('_')[0]
        logging.debug("Assuming your in country %s" % code)
        return code

    def _select_country_row(self, iter):
        path = self.liststore_countries.get_path(iter)[0]
        treeselection = self.treeview_countries.get_selection()
        treeselection.select_path(path)
        self.treeview_countries.scroll_to_cell(path)
        self.assistant.set_page_complete(self.vbox_countries, True)

    def _fill_liststore_countries(self):
        """Fille the countries liststore with all known countries"""
        lcode = self._get_current_country_from_locale()
        if not self.liststore_countries:
            self.liststore_countries = self.builder.get_object(
                                                         "liststore_countries") 
            for (country, code) in self.controller.get_provider_countries():
                if country is None:
                    country = code
                iter = self.liststore_countries.append()
                self.liststore_countries.set_value(iter, 0, country)
                self.liststore_countries.set_value(iter, 1, code)
                if code == lcode:
                    self.country_code = code
                    self._select_country_row(iter)

    def _providers_only_page_func(self, current_page):
        if current_page < self.PAGE_PROVIDERS:
            return self.PAGE_PROVIDERS
        else:
            return current_page+1

    def _all_pages_func(self, current_page):
        return current_page+1
        
    def show(self, providers=None):
        self.possible_providers = providers
        self.provider = None
    
        if not self.possible_providers:
            # No list of possible providers so allow to select the country first
            self._fill_liststore_countries()
            self.assistant.set_forward_page_func(self._all_pages_func)
        else:
            # List of possible providers given, all from the same country
            self.country_code = self.possible_providers[0].country
            self.assistant.set_forward_page_func(self._providers_only_page_func)
        self.assistant.show()

    def close(self):
        self.assistant.hide()

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

    def on_ppm_provider_assistant_prepare(self, obj, page):
        if self.assistant.get_current_page() == self.PAGE_PROVIDERS:
            if self.possible_providers:
                self._fill_provider_liststore_by_providers()
            else:
                self._fill_provider_liststore_by_country_code(self.country_code)
        elif self.assistant.get_current_page() == self.PAGE_CONFIRM:
            self.label_country.set_text(self.country_code)
            self.label_provider.set_text(self.provider)
                
    def on_treeview_countries_changed(self, obj):
        self.assistant.set_page_complete(self.vbox_countries, True)
        selection = self.treeview_countries.get_selection()
        (model, iter) = selection.get_selected()
        if not iter:
            return
        self.country_code = model.get_value(iter, 1)
                
    def on_treeview_providers_changed(self, obj):
        self.assistant.set_page_complete(self.vbox_providers, True)
        selection = self.treeview_providers.get_selection()
        (model, iter) = selection.get_selected()
        if not iter:
            return
        self.provider = model.get_value(iter, 0)

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
                'MobileBroadband/ServiceProviders\">website</a>')

    def __init__(self, main_dialog):
        self.dialog = gtk.MessageDialog(parent=main_dialog.dialog,
                                        flags=gtk.DIALOG_MODAL |
                                              gtk.DIALOG_DESTROY_WITH_PARENT,
                                        type=gtk.MESSAGE_INFO,
                                        buttons=gtk.BUTTONS_OK)
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


class PPMModemResponse(PPMObject):
    """Dialog shown while waiting for a response from the modem"""
    def __init__(self, main_dialog):
        PPMObject.__init__(self, main_dialog, "ppm-modem-request")
        self.dialog = self.builder.get_object("ppm_modem_request")
        self._add_elements("progressbar")
        self.dialog.set_transient_for(main_dialog.dialog)
        self.timer = None
        
    def show(self):
        self.timer = glib.timeout_add(50, self.do_progress,
                                      priority=glib.PRIORITY_HIGH)
        self.dialog.show()

    def close(self):
        if self.timer:
            glib.source_remove(self.timer)
            self.timer = None
        self.dialog.hide()

    def do_progress(self):
        self.progressbar.pulse()
        return True


def setup_i18n():
    locale.setlocale(locale.LC_ALL, '')
    gettext.install(ppm.gettext_app, ppm.gettext_dir)
    gettext.bindtextdomain(ppm.gettext_app, ppm.gettext_dir)
    locale.bindtextdomain(ppm.gettext_app, ppm.gettext_dir)
    _ = gettext.gettext
    logging.debug('Using locale: %s', locale.getlocale())


def setup_dbus():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)


def main():
    logging.basicConfig(level=logging.DEBUG,
                        format='ppm: %(levelname)s: %(message)s')

    setup_dbus()
    setup_i18n()

    controller = PPMController()
    main_dialog = PPMDialog(controller)
    glib.timeout_add(1, controller.setup)
    
    gtk.main()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.debug("Received KeyboardInterrupt. Exiting application.")
    except SystemExit:
        raise