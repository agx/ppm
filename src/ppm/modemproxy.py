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
#    along with this program; if not, see <http://www.gnu.org/licenses/>.

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

    DBUS_INTERFACE_PROPERTIES = 'org.freedesktop.DBus.Properties'
    DBUS_INTERFACE_OBJECT_MANAGER = 'org.freedesktop.DBus.ObjectManager'
    MM_DBUS_SERVICE = 'org.freedesktop.ModemManager1'
    MM_DBUS_INTERFACE_MODEM_MANAGER = 'org.freedesktop.ModemManager1'
    MM_DBUS_OBJECT_MODEM_MANAGER = '/org/freedesktop/ModemManager1'
    MM_DBUS_INTERFACE_MODEM = 'org.freedesktop.ModemManager1.Modem'
    MM_DBUS_INTERFACE_SIM = 'org.freedesktop.ModemManager1.Sim'
    MM_DBUS_INTERFACE_MODEM_GSM_USSD = 'org.freedesktop.ModemManager1.Modem.Modem3gpp.Ussd'
    MM_DBUS_TIMEOUT = 5000
    MM_DBUS_FLAGS = (Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES |
                     Gio.DBusProxyFlags.DO_NOT_CONNECT_SIGNALS)
    # IMSIs are 14 or 15 digits
    IMSI_RE = r'\d{14,15}'

    __gsignals__ = {
        # Emitted when a request to MM starts
        'request-started': (GObject.SignalFlags.RUN_FIRST, None,
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
        self.objs = None

    def get_objects(self):
        mm = Gio.DBusProxy.new_sync(self.bus,
                                    self.MM_DBUS_FLAGS,
                                    None,
                                    self.MM_DBUS_SERVICE,
                                    self.MM_DBUS_OBJECT_MODEM_MANAGER,
                                    self.DBUS_INTERFACE_OBJECT_MANAGER,
                                    None)
        self.objs = mm.GetManagedObjects()

    def objects(self):
        if self.objs is None:
            self.get_objects()
        return self.objs

    def set_modem(self, modem):
        self.modem = modem

    def mm_request(func):
        def wrapped_f(self, *args, **kw):
            self.request = "%s" % func.__name__
            if 'reply_func' in kw:
                self.reply_func = kw['reply_func']
            if 'error_func' in kw:
                self.error_func = kw['error_func']
            self.emit('request-started', self)
            func(self, *args, **kw)
        wrapped_f.__name__ = func.__name__
        wrapped_f.__doc__ = func.__doc__
        return wrapped_f

    def mm_request_done(func):
        def wrapped_f(self, *args, **kw):
            self.emit('request-finished', self)
            ret = func(self, *args, **kw)
            self.reply_func = None
            self.error_func = None
            self.request = None
            return ret
        wrapped_f.__name__ = func.__name__
        wrapped_f.__doc__ = func.__doc__
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
        self.get_objects()
        for path, obj in self.objects().items():
            if self.MM_DBUS_INTERFACE_MODEM in obj:
                modems.append(path)
        return modems

    def get_imsi(self):
        card = Gio.DBusProxy.new_sync(self.bus,
                                      self.MM_DBUS_FLAGS,
                                      None,
                                      self.MM_DBUS_SERVICE,
                                      self.objects()[self.modem][self.MM_DBUS_INTERFACE_MODEM]['Sim'],
                                      self.DBUS_INTERFACE_PROPERTIES,
                                      None)
        try:
            return card.Get('(ss)', self.MM_DBUS_INTERFACE_SIM, 'Imsi')
        except Exception as msg:
            raise ModemError("Getting IMSI failed: %s" % msg)
        if not re.match(self.IMSI_RE, imsi):
            raise ModemError("%s is not a valid imsi" % imsi)
        return imsi

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
