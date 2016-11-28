#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Nexcess.net python-r1soft
# Copyright (C) 2016  Nexcess.net L.L.C.
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

logger = logging.getLogger('cdp-copy-host')
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)


def cdp_lookup(obj_list, attr_name, attr_value):
    return [o for o in obj_list if getattr(o, attr_name) == attr_value][0]
    # raise ValueError()

def set_obj_attr(attr_map, key, value, cond=lambda v: True):
    for entry in attr_map.entry:
        if entry.key == key:
            if cond(value):
                entry.value = value
                return True
    else:
        return False

def cdp_copy_host(src, dest, options):
    logger.info('Copying from %s to %s', src._host, dest._host)
    src_agents = src.Agent.getAgents()
    src_disksafes = src.DiskSafe.getDiskSafes()
    src_policies = src.Policy2.getPolicies()


    dest_agents = dest.Agent.getAgents()
    dest_disksafes = dest.DiskSafe.getDiskSafes()
    dest_policies = dest.Policy2.getPolicies()
    dest_hostnames = [a.hostname for a in dest_agents]

    dest_volume = dest.Volume.getVolumes()[0]
    logger.debug('Using volume: %s', dest_volume.id)

    # for agent in agents:
    for src_policy in src_policies:
        src_policy_id = src_policy.id

        if not options.include_disabled and not src_policy.enabled:
            logger.debug('Skipping disabled policy: %s', src_policy.name)
            continue
        src_disksafe = cdp_lookup(src_disksafes, 'id', src_policy.diskSafeID)
        src_agent = cdp_lookup(src_agents, 'id', src_disksafe.agentID)
        if src_agent.hostname in dest_hostnames:
            logger.warn('Skipping already copied agent [%s]: %s',
                src_agent.hostname, src_agent.id)
            continue
        logger.info('Copying policy:%s disksafe:%s agent:%s', src_policy.id,
            src_disksafe.id, src_agent.id)

        src_agent.id = None
        if not options.include_db_plugin and src_agent.databaseAddOnEnabled:
            logger.info('Disabling db plugin for agent...')
            src_agent.databaseAddOnEnabled = False
        dest_agent = dest.Agent.createAgentWithObject(agent=src_agent)
        logger.info('Copied agent: "%s" -> %s', dest_agent.hostname, dest_agent.id)

        src_disksafe.id = None
        src_disksafe.path = None
        src_disksafe.volumeID = dest_volume.id
        src_disksafe.agentID = dest_agent.id
        if not options.include_db_plugin:
            set_obj_attr(src_disksafe.diskSafeAttributeMap, 'DATABASE_BACKUPS_ENABLED', 'false')
        if not options.include_cp_plugin:
            set_obj_attr(src_disksafe.diskSafeAttributeMap, 'CONTROLPANELS_ENABLED', 'false')
        dest_disksafe = dest.DiskSafe.createDiskSafeWithObject(disksafe=src_disksafe)
        logger.info('Copied disksafe: "%s" -> %s', dest_disksafe.description, dest_disksafe.id)

        src_policy.id = None
        src_policy.diskSafeID = dest_disksafe.id
        src_policy.exchangeSettings = None
        src_policy.SQLServerSettings = None
        if not options.include_db_plugin:
            src_policy.databaseInstanceList = []
        if not options.include_cp_plugin:
            src_policy.controlPanelInstanceList = []
        dest_policy = dest.Policy2.createPolicy(policy=src_policy)
        logger.info('Copied policy: "%s" -> %s', dest_policy.description, dest_policy.id)

        if src_policy.enabled:
            src.Policy2.disablePolicy(
                policy=src.Policy2.getPolicyById(id=src_policy_id))
            logger.info('Disabled source policy: %s', src_policy_id)


if __name__ == '__main__':
    parser = r1soft.util.build_option_parser()
    parser.remove_option('--r1soft-host')
    parser.add_option('--include-disabled',
        help='Include agents with disabled policies',
        action='store_true', default=False)
    parser.add_option('--include-db-plugin',
        help='Allow database backups via the DB plugins',
        action='store_true', default=False)
    parser.add_option('--include-cp-plugin',
        help='Allow control panel plugin',
        action='store_true', default=False)

    opts, args = parser.parse_args()

    src_host, dest_host = args[:2]
    src = r1soft.cdp3.CDP3Client(src_host, opts.username, opts.password)
    dest = r1soft.cdp3.CDP3Client(dest_host, opts.username, opts.password)

    cdp_copy_host(src, dest, opts)
