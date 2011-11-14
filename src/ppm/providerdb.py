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

import os
import logging
from lxml import etree

from provider import Provider

class ProviderDB(object):
    """Proxy to mobile broadband provider database"""

    provider_info = os.getenv('PPM_PROVIDER_DB',
                              '/usr/share/mobile-broadband-provider-info/'
                              'serviceproviders.xml')
    country_codes = '/usr/share/zoneinfo/iso3166.tab'

    def __init__(self):
        self.__tree = None
        self.__countries = {}

    @property
    def tree(self):
        if self.__tree:
            return self.__tree
        else:
            self.__tree = etree.parse(self.provider_info)
            return self.__tree

    @property
    def countries(self):
        if self.__countries:
            return self.__countries
        else:
            self._tree = self._load_countries()
            return self.__countries
        
    def _load_countries(self):
        try:
            for line in file(self.country_codes, 'r'):
                if line[0] != '#':
                    (code, country) = line.split('\t',2)
                    self.__countries[code.lower()] = country.strip()
        except IOError as msg:
            logging.warning("Loading country code database failed: %s" % msg)

    def _fill_provider_info(self, provider_elem):
        """Fill a provider object with data from the XML"""
        name = provider_elem.xpath("./name")[0].text
        country = provider_elem.getparent().attrib['code']
        gsm_elem = provider_elem.xpath("./gsm")
        provider = Provider(country = country,
                            name = name)
        if gsm_elem:
            self._fill_balance_check_cmd(gsm_elem[0], provider)
            self._fill_top_up_cmd(gsm_elem[0], provider)
        return provider

    def _fill_balance_check_cmd(self, xmlelemnt, provider):
        """Fetch balance check method from XML and add it to the provider"""
        for child in xmlelemnt.iter(tag='balance-check'):
            check_types = child.getchildren()
            for t in check_types:
                if t.tag == 'ussd':
                    sequence = t.text
                    provider.add_fetch_balance_cmd({'ussd': sequence})
                if t.tag == 'sms':
                    number = t.text
                    text = t.attrib['text']
                    provider.add_fetch_balance_cmd({'sms': (number, text)})

    def _fill_top_up_cmd(self, xmlelement, provider):
        for child in xmlelement.iter(tag='balance-top-up'):
            check_types = child.getchildren()
            for t in check_types:
                if t.tag == 'ussd':
                    sequence = t.text
                    replacement = t.attrib['replacement']
                    provider.add_top_up_cmd({'ussd': [sequence, replacement]})
                if t.tag == 'sms':
                    number = t.text
                    text = t.attrib['text']
                    provider.add_top_up_cmd({'sms': (number, text)})
                    
    def get_providers(self, mcc, mnc):
        """
        Get possible providers for the current mcc and mnc from the database
        """
        path = "//network-id[@mcc='%s' and @mnc='%s']" % (mcc, mnc)
        searcher = etree.ETXPath(path)
        providers = []

        try:
            for r in searcher(self.tree):
                provider_elem = r.getparent().getparent()
                providers.append(self._fill_provider_info(provider_elem))
        except etree.XMLSyntaxError:
            return None
        return providers

    def get_provider(self, country_code, name):
        path = "//country[@code='%s']/provider[name='%s']" % (country_code, name)
        searcher = etree.ETXPath(path)

        for r in searcher(self.tree):
            return self._fill_provider_info(r)
        return None
        
    def get_country_codes(self):
        path = "/serviceproviders/country"
        searcher = etree.ETXPath(path)

        for r in searcher(self.tree):
            yield r.attrib['code']

    def get_countries(self):
        for code in self.get_country_codes():
            try:
                yield (self.countries[code], code)
            except KeyError:
                yield (None, code)
    
    def get_providers_by_code(self, country_code):
        path = ("/serviceproviders/country[@code='%s']/provider/name" %
                country_code)
        searcher = etree.ETXPath(path)

        for r in searcher(self.tree):
            yield r.text
