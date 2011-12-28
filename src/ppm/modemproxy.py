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

from gi.repository import GObject
from gi.repository import GLib
from gi.repository import Gio


class ModemError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def is_forbidden(self):
        return [False, True][self.msg.find("Operation not allowed") != -1]

    def is_disabled(self):
         return [False, True][self.msg.find("not enabled") != -1]


class ModemManagerProxy(GObject.GObject):
    """Interface to ModemManager DBus API
    @ivar request: current pending request to ModemManager
    @type request: string
    @ivar modem: dbus path of modem we're currently acting on
    @type modem: string
    """

    MM_DBUS_SERVICE='org.freedesktop.ModemManager'
    MM_DBUS_INTERFACE_MODEM_MANAGER='org.freedesktop.ModemManager'
    MM_DBUS_OBJECT_MODEM_MANAGER='/org/freedesktop/ModemManager'
    MM_DBUS_INTERFACE_MODEM='org.freedesktop.ModemManager.Modem'
    MM_DBUS_INTERFACE_MODEM_GSM_CARD='org.freedesktop.ModemManager.Modem.Gsm.Card'
    MM_DBUS_INTERFACE_MODEM_GSM_USSD='org.freedesktop.ModemManager.Modem.Gsm.Ussd'
    MM_DBUS_TIMEOUT = 5000
    MM_DBUS_FLAGS = (Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES |
                     Gio.DBusProxyFlags.DO_NOT_CONNECT_SIGNALS)

    __gsignals__ = {
        # Emitted when a request to MM starts
        'request-started':  (GObject.SignalFlags.RUN_FIRST, None,
                             [object]),
        # Emitted when a request has finished
        'request-finished': (GObject.SignalFlags.RUN_FIRST, None,
                             [object]),
        }

    def __init__(self):
        GObject.GObject.__init__(self)
        self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self.request = None
        self.reply_func = None
        self.error_func = None
        self.modem = None
        self.obj = None

    def set_modem(self, modem):
        self.modem = modem

    def mm_request(func):
        def wrapped_f( self, *args, **kw):
            self.request = "%s" % func.func_name
            if kw.has_key('reply_func'):
                self.reply_func = kw['reply_func']
            if kw.has_key('error_func'):
                self.error_func = kw['error_func']
            self.emit('request-started', self)
            func(self, *args, **kw)
        wrapped_f.__name__= func.__name__
        wrapped_f.__doc__= func.__doc__
        return wrapped_f

    def mm_request_done(func):
        def wrapped_f( self, *args, **kw):
            self.emit('request-finished', self)
            ret = func(self, *args, **kw)
            self.reply_func = None
            self.error_func = None
            self.request = None
            return ret
        wrapped_f.__name__= func.__name__
        wrapped_f.__doc__= func.__doc__
        return wrapped_f

    def request_pending(self):
        if self.request:
            return True
        else:
            return False

    @mm_request_done
    def handle_dbus_reply(self, obj, result, user_data):
        try:
            res = obj.call_finish(result)
            if self.reply_func:
                self.reply_func(res, user_data)
        except Exception as err:
            if self.error_func:
                me = ModemError("%s failed: %s" % (self.request, err))
                self.error_func(me)

    def get_modems(self):
        modems = []
        mm = Gio.DBusProxy.new_sync(self.bus,
                                    self.MM_DBUS_FLAGS,
                                    None,
                                    self.MM_DBUS_SERVICE,
                                    self.MM_DBUS_OBJECT_MODEM_MANAGER,
                                    self.MM_DBUS_INTERFACE_MODEM_MANAGER,
                                    None)
        ret = mm.EnumerateDevices()
        for modem in ret:
            modems.append(modem)
        return modems

    def get_imsi(self):
        card = Gio.DBusProxy.new_sync(self.bus,
                                      self.MM_DBUS_FLAGS,
                                      None,
                                      self.MM_DBUS_SERVICE,
                                      self.modem,
                                      self.MM_DBUS_INTERFACE_MODEM_GSM_CARD,
                                      None)
        try:
            return card.GetImsi()
        except Exception as msg:
            raise ModemError("Getting IMSI failed: %s" % msg)

    def get_network_id(self):
        imsi = self.get_imsi()
        mcc = imsi[0:3]
        mnc = imsi[3:5]
        return (mcc, mnc)

    @mm_request
    def ussd_initiate(self, command, reply_func=None, error_func=None):
        ussd = Gio.DBusProxy.new_sync(self.bus,
                                      self.MM_DBUS_FLAGS,
                                      None,
                                      self.MM_DBUS_SERVICE,
                                      self.modem,
                                      self.MM_DBUS_INTERFACE_MODEM_GSM_USSD,
                                      None)
        ussd.call("Initiate", GLib.Variant('(s)', (command,)),
                  Gio.DBusCallFlags.NO_AUTO_START, self.MM_DBUS_TIMEOUT, None,
                  self.handle_dbus_reply, None)

    @mm_request
    def _modem__enable(self, enable, reply_func=None, error_func=None):
        ussd = Gio.DBusProxy.new_sync(self.bus,
                                      self.MM_DBUS_FLAGS,
                                      None,
                                      self.MM_DBUS_SERVICE,
                                      self.modem,
                                      self.MM_DBUS_INTERFACE_MODEM,
                                      None)
        ussd.call("Enable", GLib.Variant('(b)', (enable,)),
                  Gio.DBusCallFlags.NO_AUTO_START, self.MM_DBUS_TIMEOUT, None,
                  self.handle_dbus_reply, None)

    def modem_enable(self, reply_func=None, error_func=None):
        self._modem__enable(True,
                            reply_func=reply_func,
                            error_func=error_func)

    def modem_disable(self, reply_func=None, error_func=None):
        self._modem_enable(False,
                           reply_func=reply_func,
                           error_func=error_func)

GObject.type_register(ModemManagerProxy)
