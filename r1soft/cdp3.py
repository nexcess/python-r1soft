# -*- coding: utf-8 -*-

# Nexcess.net python-r1soft
# Copyright (C) 2013  Nexcess.net L.L.C.
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

import logging
import suds
import functools
import time

logger = logging.getLogger('r1soft.cdp3')

def build_wsdl_url(host, namespace, port=None, ssl=True):
    """Build WSDL URL for CDP3+ API
    """

    proto = 'https' if ssl else 'http'
    if port is None:
        port = CDP3Client.PORT_HTTPS if ssl else CDP3Client.PORT_HTTP

    url = '{proto}://{host}:{port}/{namespace}?wsdl'.format(
        proto=proto,
        host=host,
        port=port,
        namespace=namespace
    )
    logger.debug('Built WSDL url: %s', url)
    return url

class SoapClientProxy(object):
    def __init__(self, real_client, rate_limit=8.0, backwards_compat=True):
        self._real_client = real_client
        self._rl_hz = 1.0 / (rate_limit * 1.0)
        self._rl_prev = time.time()
        if backwards_compat:
            # self.service = self._real_client.service
            # self.factory = self._real_client.factory
            self.service = self
            self.factory = self

    def __getattr__(self, name):
        func = getattr(self._real_client.service, name)
        # @functools.wraps(func)
        def rate_limit_wrapper(*args, **kwargs):
            now = time.time()
            delta = max(0, now - self._rl_prev)
            if delta < self._rl_hz:
                time.sleep(self._rl_hz - delta)
            self._rl_prev = time.time()
            return func(*args, **kwargs)
        return rate_limit_wrapper

    def __call__(self, *args, **kwargs):
        return self._real_client.factory.create(*args, **kwargs)
    create = __call__

class CDP3Client(object):
    """SOAP client for CDP3+ API
    """

    PORT_HTTP   = 9080
    PORT_HTTPS  = 9443

    def __init__(self, host, username, password, port=None, ssl=True, **kwargs):
        self.__namespaces = {}
        self._host = host
        self._username = username
        self._password = password
        self._port = port
        self._ssl = ssl
        self._init_args = kwargs

    def __getattr__(self, name):
        logger.debug('Loading SOAP client for namespace: %s', name)
        ns = self.__namespaces.get(name, None)
        if ns is None:
            logger.debug('Client doesn\'t exist, creating client for ' \
                'namespace: %s', name)
            ns = SoapClientProxy(suds.client.Client(
                build_wsdl_url(self._host, name, self._port, self._ssl),
                username=self._username,
                password=self._password,
                **self._init_args))
            self.__namespaces[name] = ns
        return ns

    def build_object(self, namespace, object_type, attributes):
        object_instance = getattr(self, namespace).factory.create(object_type)

        for key, value in attributes.iteritems():
            if type(value) == tuple:
                attr_type = getattr(self, namespace).factory.create(value[0])
                attr_value = getattr(attr_type, value[1])
                setattr(object_instance, key, attr_value)
            else:
                setattr(object_instance, key, value)

        return object_instance
