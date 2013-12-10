#!/usr/bin/env python

import suds.client
import logging

logger = logging.getLogger('cdp-add-agent')
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)
logger.propagate = False

class MetaClient(object):
    def __init__(self, url_base, **kwargs):
        self.__url_base = url_base
        self.__init_args = kwargs
        self.__clients = dict()

    def __getattr__(self, name):
        c = self.__clients.get(name, None)
        logger.debug('Accessing SOAP client: %s' % name)
        if c is None:
            logger.debug('Client doesn\'t exist, creating: %s' % name)
            c = suds.client.Client(self.__url_base % name, **self.__init_args)
            self.__clients[name] = c
        return c

def get_wsdl_url(hostname, namespace, use_ssl=True, port_override=None):
    if use_ssl:
        proto = 'https'
    else:
        proto = 'http'
    if port_override is None:
        if use_ssl:
            port = 9443
        else:
            port = 9080
    else:
        port = port_override
    url = '%s://%s:%d/%s?wsdl' % (proto, hostname, port, namespace)
    logging.debug('Creating WSDL URL: %s' % url)
    return url

if __name__ == '__main__':
    import sys
    import optparse
    import os

    parser = optparse.OptionParser()
    parser.add_option('-r', '--r1soft-host', dest='cdp_host',
        help='R1Soft server to add host to')
    parser.add_option('-u', '--username', dest='username',
        default=os.environ.get('CDP_USER', 'admin'),
        help='R1Soft server API username')
    parser.add_option('-p', '--password', dest='password',
        default=os.environ.get('CDP_PASS', ''),
        help='R1Soft server API password')
    parser.add_option('-d', '--description', dest='description',
        default=None,
        help='Custom description field, default is the same as hostname, applied to all hosts')
    parser.add_option('-D', '--use-db-addon', dest='use_db_addon',
        action='store_true', default=False,
        help='Use the CDP DB addon')
    parser.add_option('--db-user', dest='sqluser',
        help='MySQL user for DB addon')
    parser.add_option('--db-pass', dest='sqlpass',
        help='MySQL pass for DB addon')
    parser.add_option('-R', '--recovery-point-limit', dest='recovery_point_limit',
        type=int, default=30,
        help='Number of recovery points to keep')
    options, args = parser.parse_args()

    cdp_host = options.cdp_host
    username = options.username
    password = options.password
    use_db_addon = options.use_db_addon
    recovery_point_limit = options.recovery_point_limit
    sqluser = options.sqluser
    sqlpass = options.sqlpass
    for hostname in args:
        if options.description is None:
            description = hostname
        else:
            description = '%s (%s)' % (options.description, hostname)
        logger.info('Setting up backups for host (%s) on CDP server (%s) with description: %s',
            hostname, cdp_host, description)
        client = MetaClient(get_wsdl_url(cdp_host, '%s'),
            username=username, password=password)
        logger.debug('Creating special types...')
        DiskSafeObject = client.DiskSafe.factory.create('diskSafe.disksafe')
        CompressionType = client.DiskSafe.factory.create('diskSafe.compressionType')
        CompressionLevel = client.DiskSafe.factory.create('diskSafe.compressionLevel')
        DeviceBackupType = client.DiskSafe.factory.create('diskSafe.deviceBackupType')
        FrequencyType = client.Policy2.factory.create('frequencyType')
        FrequencyValues = client.Policy2.factory.create('frequencyValues')
        logger.debug('Created special types')
        logger.debug('Getting volumes...')
        volumes = client.Volume.service.getVolumes()
        volume = volumes[0]
        logger.info('Found %d volumes, using volume %s', len(volumes), volume.name)
        logger.debug('Creating agent for host: %s', hostname)
        agent = client.Agent.service.createAgent(
            hostname=hostname,
            portNumber=1167,
            description=description,
            databaseAddOnEnabled=use_db_addon
        )
        logger.info('Created agent for host (%s) with ID: %s', hostname, agent.id)
        logger.debug('Creating disksafe for agent (%s) on volume (%s)', agent.id, volume.id)
        DiskSafeObject.description = hostname
        DiskSafeObject.agentID = agent.id
        DiskSafeObject.volumeID = volume.id
        DiskSafeObject.compressionType = CompressionType.QUICKLZ
        DiskSafeObject.compressionLevel = CompressionLevel.LOW
        DiskSafeObject.deviceBackupType = DeviceBackupType.AUTO_ADD_DEVICES
        DiskSafeObject.backupPartitionTable = True
        DiskSafeObject.backupUnmountedDevices = False
        disksafe = client.DiskSafe.service.createDiskSafeWithObject(DiskSafeObject)
        logger.info('Created disksafe with ID: %s', disksafe.id)
        FrequencyValues.hoursOfDay = [0]
        FrequencyValues.startingMinute = 0
        logger.debug('Creating policy for agent (%s) on disksafe (%s)',
            hostname, disksafe.id)
        policy = client.Policy2.factory.create('policy')
        policy.enabled = True
        policy.name = hostname
        policy.description = description
        policy.diskSafeID = disksafe.id
        policy.mergeScheduleFrequencyType = FrequencyType.ON_DEMAND
        policy.replicationScheduleFrequencyType = FrequencyType.DAILY
        policy.replicationScheduleFrequencyValues = FrequencyValues
        policy.recoveryPointLimit = recovery_point_limit
        policy.forceFullBlockScan = False
        if use_db_addon:
            dbi = client.Policy2.factory.create('databaseInstance')
            dbi.dataBaseType = client.Policy2.factory.create('dataBaseType').MYSQL
            dbi.enabled = True
            dbi.hostName = '127.0.0.1'
            dbi.name = 'default'
            dbi.username = sqluser
            dbi.password = sqlpass
            dbi.portNumber = 3306
            dbi.useAlternateDataDirectory = False
            dbi.useAlternateHostname = True
            dbi.useAlternateInstallDirectory = False
            policy.databaseInstanceList = [dbi]

        policy = client.Policy2.service.createPolicy(policy=policy)
        logger.info('Created policy with ID: %s', policy.id)
        logger.info('Finished setting up backups for host: %s', hostname)
