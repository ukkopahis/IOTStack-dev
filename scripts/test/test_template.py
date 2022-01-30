import sys
import unittest
from pathlib import Path
import template

class TemplateFileTestCase(unittest.TestCase):

    def setUp(self):
        self.t = template.TemplateFile(Path(
            'scripts/test/template_test/mockservice/service.yml'))

    def test_yml_view(self):
        view = sorted(self.t.yml_view.items())
        self.assertIn(('mockservice.privileged', True,), view)
        self.assertIn(('mockservice.devices./dev/ttyAMA0:ro','/dev/ttyAMA1'), view)
        self.assertIn(('mockservice.devices./dev/null','/dev/null'), view)

    def test_public_ports(self):
        self.assertEqual(self.t.public_ports(), {'8089', '53'})

    def test_variable_items(self):
        self.assertEqual(
            self.t.variable_items(),
            {'mockservice.environment.PW': '%randomPassword%'})

    def test_with_variables(self):
        res = self.t.with_variables(
            {'mockservice.environment.PW': 'testpass' })
        self.assertEqual(res.yml_view.get('mockservice.environment.PW'),
                         'testpass')
        self.test_variable_items() # check that original is unchanged
        self.assertRaises(ValueError, lambda: self.t.with_variables({}))

class NestedDictListTestCase(unittest.TestCase):

    def setUp(self):
        self.query = template.NestedDictList({
            'version': 3.0,
            'pihole': {
                'image': 'pihole/image:=1',
                'environment': [ 'FOO=BAR', 'PW=%tag%', 'E='],
                'ports': ['127.0.0.1:8080:80', '8053:53/udp', '443:443'],
                'volumes': [
                    './volumes/pihole:/config',
                    '/etc/host-timezone:/etc/timezone:ro'],
                'devices': ['/dev/sda:/dev/xvda:rwm', '/dev/null'],
                'networks': ['iotstack'],
                'privileged': True
            }
        })
        self.leaf_count = 14

    def test_items(self):
        #print( list(self.query.items()) )
        self.assertIn(('pihole.image','pihole/image:=1'),
                      list(self.query.items()))

    def test_get(self):
        self.assertRaises( KeyError, lambda: self.query.get('non-existant'))
        self.assertEqual( self.query.get('version'), 3.0)
        self.assertEqual( self.query.get('pihole.image'), 'pihole/image:=1')
        self.assertEqual( self.query.get('pihole.environment.FOO'), 'BAR')
        self.assertEqual( self.query.get('pihole.environment.PW'), '%tag%')
        self.assertEqual( self.query.get('pihole.environment.E'), '')
        self.assertEqual( self.query.get('pihole.ports.80'), '127.0.0.1:8080')
        self.assertEqual( self.query.get('pihole.ports.53/udp'), '8053')
        self.assertEqual( self.query.get('pihole.ports.443'), '443')
        self.assertEqual( self.query.get('pihole.volumes./config'), './volumes/pihole')
        self.assertEqual( self.query.get('pihole.volumes./etc/timezone:ro'), '/etc/host-timezone')
        self.assertEqual( self.query.get('pihole.devices./dev/xvda:rwm'), '/dev/sda')
        self.assertEqual( self.query.get('pihole.devices./dev/null'), '/dev/null')
        self.assertEqual( self.query.get('pihole.networks.0'), 'iotstack')
        self.assertEqual( self.query.get('pihole.privileged'), True)
        self.assertEqual( len(self.query), self.leaf_count)

    def test_set(self):
        self.query.set('version', 3.1)
        self.assertEqual( self.query.get('version'), 3.1)
        self.query.set('pihole.environment.PW', 'SECRET')
        self.assertEqual( self.query.get('pihole.environment.PW'), 'SECRET')
        self.query.set('pihole.environment.E', '1')
        self.assertEqual( self.query.get('pihole.environment.E'), '1')
        self.query.set('pihole.volumes./config', './volumes/pi-hole')
        self.assertEqual( self.query.get('pihole.volumes./config'), './volumes/pi-hole')
        self.query.set('pihole.ports.80', '8181')
        self.assertEqual( self.query.get('pihole.ports.80'), '8181')
        self.query.set('pihole.volumes./etc/timezone:ro', '/customtz')
        self.assertEqual( self.query.get('pihole.volumes./etc/timezone:ro'), '/customtz')
        self.query.set('pihole.ports.53/udp', '53')
        self.assertEqual( self.query.get('pihole.ports.53/udp'), '53')
        self.query.set('pihole.networks.0', 'private')
        self.assertEqual( self.query.get('pihole.networks.0'), 'private')
        self.query.set('pihole.devices./dev/null','/thief')
        self.assertEqual( self.query.get('pihole.devices./dev/null'), '/thief')
        self.query.set('pihole.privileged', False)
        self.assertEqual( self.query.get('pihole.privileged'), False)
        self.assertRaises(ValueError, lambda: self.query.set('service.none.existant', 0))
        self.assertEqual( len(self.query), self.leaf_count) # no new elements

