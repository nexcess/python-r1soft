#!/usr/bin/env python
import sys
import suds.client

c = suds.client.Client('https://%s:9443/Policy?wsdl' % sys.argv[1],
    username=sys.argv[2], password=sys.argv[3])
for p in c.service.getPolicies():
    if p.recoveryPointLimit != 30:
        print 'Updating %s from %d to 30' % (p.description, p.recoveryPointLimit)
        p.recoveryPointLimit = 30
        c.service.updatePolicy(p)
