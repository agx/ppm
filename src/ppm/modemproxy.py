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
import dbus.glib
import dbus.service
import gobject


class ModemError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def is_forbidden(self):
        return [False, True][self.msg.find("Operation not allowed") != -1]
                       
    def is_disabled(self):
         return [False, True][self.msg.find("not enabled") != -1]


class ModemManagerProxy(gobject.GObject):
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
    
    __gsignals__ = {
        # Emitted when we got the new account balance from the provider
        'request-started':  (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                             [object]),
        'request-finished': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                             [object]),
        }

    def __init__(self):
        self.__gobject_init__()
        self.bus = dbus.SystemBus()
        self.request = None
        self.reply_func = None
        self.error_func = None
        self.modem = None
        self.obj = None

    def set_modem(self, modem):
        self.modem = modem
        self.obj = self.bus.get_object(self.MM_DBUS_SERVICE, self.modem)

    def mm_request(func):
        def wrapped_f( self, *args, **kw) :
            self.request = "%s" % func.func_name
            if kw.has_key('reply_func'):
                self.reply_func = kw['reply_func']
            if kw.has_key('error_func'):
                self.error_func = kw['error_func']
            self.emit('request-started', self)
            ret = func(self, *args, **kw)
            return ret
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
    def handle_dbus_reply(self, *args):
        if self.reply_func:
            self.reply_func(*args)

    @mm_request_done
    def handle_dbus_error(self, e):
        if self.error_func:
            me = ModemError("%s failed: %s" % (self.request, e))
            self.error_func(me)
    
    def get_modems(self):
        modems = []        
        proxy = self.bus.get_object(self.MM_DBUS_SERVICE,
                                    self.MM_DBUS_OBJECT_MODEM_MANAGER)
        mm = dbus.Interface(proxy,
                            dbus_interface=self.MM_DBUS_INTERFACE_MODEM_MANAGER)
        ret = mm.EnumerateDevices()
        for modem in ret:
            modems.append(modem)
        return modems

    def get_imsi(self):
        card = dbus.Interface(self.obj,
                        dbus_interface=self.MM_DBUS_INTERFACE_MODEM_GSM_CARD)
        try:
            return card.GetImsi()
        except dbus.exceptions.DBusException as msg:
            raise ModemError("Getting IMSI failed: %s" % msg)

    def get_network_id(self):
        imsi = self.get_imsi()
        mcc = imsi[0:3]
        mnc = imsi[3:5]
        return (mcc, mnc)

    @mm_request
    def ussd_initiate(self, command, reply_func=None, error_func=None):
        ussd = dbus.Interface(self.obj,
                        dbus_interface=self.MM_DBUS_INTERFACE_MODEM_GSM_USSD)
        return ussd.Initiate(command,
                             reply_handler=self.handle_dbus_reply,
                             error_handler=self.handle_dbus_error)

    @mm_request
    def _modem__enable(self, enable, reply_func=None, error_func=None):
        ussd = dbus.Interface(self.obj,
                        dbus_interface=self.MM_DBUS_INTERFACE_MODEM)
        ussd.Enable(enable,
                    reply_handler=self.handle_dbus_reply,
                    error_handler=self.handle_dbus_error)
        
    def modem_enable(self, reply_func=None, error_func=None):
        self._modem__enable(True)

    def modem_disable(self, reply_func=None, error_func=None):
        self._modem_enable(False)

gobject.type_register(ModemManagerProxy)
