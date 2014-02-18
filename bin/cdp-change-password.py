#!/usr/bin/env python
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

import r1soft

logger = logging.getLogger('cdp-change-password')
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)
logger.propagate = False

def handle_cdp3_server(server, username, new_password):
    updated = False
    client = r1soft.util.build_cdp3_client(server)
    logger.info('Checking users on server: %s', server['hostname'])
    users = client.User.service.getUsers()

    for user in (u for u in users if u.username == username):
        logger.info('Updating user: %s (%s)', user.username, user.id)
        user.password = new_password
        client.User.service.updateUser(user)
        updated = True
    return updated

def handle_cdp2_server(server, username, new_password):
    updated = False
    return updated

if __name__ == '__main__':
    import sys

    try:
        username, new_password = sys.argv[1].split(':')
        config_file = sys.argv[2]
    except IndexError:
        logger.error('Usage: %s <username>:<new password> <config file>')
        sys.exit(1)

    config = r1soft.util.read_config(config_file)

    handler_map = {
        2: lambda server: handle_cdp2_server(server, username, new_password),
        3: lambda server: handle_cdp3_server(server, username, new_password),
        5: lambda server: handle_cdp3_server(server, username, new_password),
    }

    for (server, results) in r1soft.util.dispatch_handlers(config,
            lambda s: handler_map.get(s['version'])(s)):
        print '%s: %s' % (server['hostname'], results)
