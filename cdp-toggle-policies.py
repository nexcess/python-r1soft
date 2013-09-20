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

import r1soft


def get_clients(config):
    return dict((server['hostname'], r1soft.util.build_cdp3_client(server)) \
        for server in config if server['version'] > 2)

def get_policies(clients):
    print 'Loading policy lists, this may take a while...'
    def get_policies_helper(hostname, client):
        try:
            return client.Policy2.service.getPolicies()
        except Exception as err:
            print 'Error loading policies (%s): %s' % (hostname, err)
            return []
    return dict((hostname, get_policies_helper(hostname, client)) \
        for hostname, client in clients.iteritems())

def filter_policies(server, policies):
    return dict((hostname, [p for p in policy_list \
            if server == p.name]) \
        for hostname, policy_list in policies.iteritems())

def toggle_policy_list(clients, selected_policies, enable):
    for hostname, policy_list in selected_policies.iteritems():
        for policy in [p for p in policy_list if p.enabled != enable]:
            try:
                if enable:
                    print 'Enabling policy (%s) on server: %s' % (policy.name, hostname)
                    clients[hostname].Policy2.service.enablePolicy(policy)
                else:
                    print 'Disabling policy (%s) on server: %s' % (policy.name, hostname)
                    clients[hostname].Policy2.service.disablePolicy(policy)
            except Exception as err:
                print 'Error on policy: %s' % policy.name

def toggle_policies(config, server_list, enable):
    clients = get_clients(config)
    policies = get_policies(clients)

    for server in server_list:
        toggle_policy_list(clients, filter_policies(server, policies), enable)

if __name__ == '__main__':
    import sys

    try:
        enable_policies = sys.argv[1] == '--enable'
        config_filename = sys.argv[2]
        server_list_filename = sys.argv[3]
    except IndexError:
        print 'Usage: %s [--enable|--disable] <config file> <server list file>' % sys.argv[0]
        sys.exit(1)

    config = r1soft.util.read_config(config_filename)
    # skip the first line (headings) and get the 4th field in every row
    # (the hostname)
    with open(server_list_filename) as slf:
        server_list = [line.strip().split(',')[3] \
            for line in slf.read().strip().split('\n')[1:]]

    toggle_policies(config, server_list, enable_policies)
