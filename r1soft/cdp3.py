# -*- coding: utf-8 -*-

# Nexcess.net Turpentine Extension for Magento
# Copyright (C) 2012  Nexcess.net L.L.C.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import suds

def build_wsdl_url(host, namespace, port=None, ssl=True):
    """Build WSDL URL for CDP3+ API
    """

    proto = 'https' if ssl else 'http'
    if port is None:
        port = 9443 if ssl else 9080

    url = '{proto}://{host}:{port}/{namespace}?wsdl'.format(
        proto=proto,
        host=host,
        port=port,
        namespace=namespace
    )


class CDP3Client(object):
    """SOAP client for CDP3+ API
    """

    __namespaces = {}

    def __init__(self, host, port=None, ssl=True, **kwargs):
        self._host = host
        self._port = port
        self._ssl = ssl
        self._init_args = kwargs

    def __getattr__(self, name):
        ns = self.__namespaces.get(name, None)
        if ns is None:
            ns = suds.client.Client(
                build_wsdl_url(self._host, ns, self._port, self._ssl),
                **self._init_args)
            self.__namespaces[name] = ns
        return ns
