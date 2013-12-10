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
import re

import r1soft

logger = logging.getLogger('cdp-add-agent')
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)
logger.propagate = False

DB_PLUGIN_CANDIDATES_RE = re.compile(
    r'(?:mce\d+|[\w\d]{2,3})-db|(?:obp|sip|eep)(?:uk|au)?[1-6]-\d+|sip4[a-z]-db')

def handle_cdp3_server(server, db_username, db_password):
    logger.info('Checking DB plugin for agents on server %s', server['hostname'])
    client = r1soft.util.build_cdp3_client(server)

    policies = client.Policy2.service.getPolicies()
    disk_safes = client.DiskSafe.service.getDiskSafes()
    for agent in client.Agent.service.getAgents():
        if DB_PLUGIN_CANDIDATES_RE.match(agent.hostname) or \
                DB_PLUGIN_CANDIDATES_RE.match(agent.description):
            if not agent.databaseAddOnEnabled:
                logger.info('Enabling DB plugin for agent: %s', agent.hostname)
                agent.databaseAddOnEnabled = True
                client.Agent.service.updateAgent(agent)
            agent_disk_safes = [ds for ds in disk_safes if ds.agentID == agent.id]
            agent_policies = [p for p in policies \
                if p.enabled and hasattr(p, 'diskSafeID') and \
                    p.diskSafeID in [ds.id for ds in agent_disk_safes]]
            for policy in agent_policies:
                if not (hasattr(policy, 'databaseInstanceList') and \
                        len(policy.databaseInstanceList) > 0):
                    logger.info('Adding DB to agent (%s) policy %s (%s)',
                        agent.hostname, policy.name, policy.id)
                    db_instance = client.Policy2.factory.create('databaseInstance')
                    db_instance.dataBaseType = client.Policy2.factory.create('dataBaseType').MYSQL
                    db_instance.enabled = True
                    db_instance.hostName = '127.0.0.1'
                    db_instance.name = 'default'
                    db_instance.username = db_username
                    db_instance.password = db_password
                    db_instance.portNumber = 3306
                    db_instance.useAlternateDataDirectory = False
                    db_instance.useAlternateHostname = True
                    db_instance.useAlternateInstallDirectory = False
                    policy.databaseInstanceList = [db_instance]
                    client.Policy2.service.updatePolicy(policy=policy)

def handle_cdp5_server(server, db_username, db_password):
    logger.info('Checking DB plugin for agents on server %s', server['hostname'])
    client = r1soft.util.build_cdp3_client(server)

    policies = client.Policy2.service.getPolicies()
    disk_safes = client.DiskSafe.service.getDiskSafes()
    for agent in client.Agent.service.getAgents():
        if DB_PLUGIN_CANDIDATES_RE.match(agent.hostname) or \
                DB_PLUGIN_CANDIDATES_RE.match(agent.description):
            if not agent.databaseAddOnEnabled:
                logger.info('Enabling DB plugin for agent: %s', agent.hostname)
                agent.databaseAddOnEnabled = True
                client.Agent.service.updateAgent(agent)
            agent_disk_safes = [ds for ds in disk_safes if ds.agentID == agent.id]
            agent_policies = [p for p in policies \
                if p.enabled and hasattr(p, 'diskSafeID') and \
                    p.diskSafeID in [ds.id for ds in agent_disk_safes]]
            for policy in agent_policies:
                if not (hasattr(policy, 'databaseInstanceList') and \
                        len(policy.databaseInstanceList) > 0):
                    logger.info('Adding DB to agent (%s) policy %s (%s)',
                        agent.hostname, policy.name, policy.id)
                    db_instance = client.Policy2.factory.create('databaseInstance')
                    db_instance.dataBaseType = client.Policy2.factory.create('dataBaseType').MYSQL
                    db_instance.enabled = True
                    db_instance.hostName = '127.0.0.1'
                    db_instance.name = 'default'
                    db_instance.username = db_username
                    db_instance.password = db_password
                    db_instance.portNumber = 3306
                    db_instance.useAlternateDataDirectory = False
                    db_instance.useAlternateHostname = True
                    db_instance.useAlternateInstallDirectory = False
                    policy.databaseInstanceList = [db_instance]
                    del policy.exchangeSettings
                    client.Policy2.service.updatePolicy(policy=policy)

if __name__ == '__main__':
    import sys

    try:
        db_user, db_pass = sys.argv[1].split(':')
        config_file = sys.argv[2]
    except IndexError:
        logger.error('Usage: %s <MySQL user>:<MySQL pass> <config file>' % sys.argv[0])
        sys.exit(1)

    config = r1soft.util.read_config(config_file)

    handler_map = {
        3: lambda server: handle_cdp3_server(server, db_user, db_pass),
        5: lambda server: handle_cdp5_server(server, db_user, db_pass),
    }

    dummy_func = lambda server: (server, lambda: None)
    for (server, handler) in r1soft.util.dispatch_handlers(config, handler_map,
            dummy_func):
        try:
            handler()
        except Exception as err:
            logger.exception(err)
