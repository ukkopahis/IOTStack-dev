import sys
import unittest
import template

class TemplateFileTestCase(unittest.TestCase):

    def setUp(self):
        self.t = template.TemplateFile(
            'scripts/test/template_test/mockservice/service.yml')

    def test_mockservice(self):
        self.assertEqual(self.t.public_ports(), {'8089', '53'})

    def test_get_variable_items(self):
        self.assertEqual(
            self.t.get_variable_items(),
            {'mockservice.environment.PW': '%randomPassword%'})

    def test_with_variables(self):
        res = self.t.with_variables(
            {'mockservice.environment.PW': 'testpass' })
        self.assertEqual(res.yml_view.get('mockservice.environment.PW'),
                         'testpass')
        self.assertRaises(ValueError, lambda: self.t.with_variables({}))

class NestedDictListTestCase(unittest.TestCase):

    def setUp(self):
        self.query = template.NestedDictList({
            'version': 3.0,
            'pihole': {
                'image': 'pihole/image:latest',
                'environment': [ 'FOO=BAR', 'PW=%tag%', 'E='],
                'ports': ['127.0.0.1:8080:80', '8053:53/udp', '443:443'],
                'volumes': [
                    './volumes/pihole:/config',
                    '/etc/timezone:/etc/timezone:ro'],
                'networks': ['iotstack']
            }
        })

    def test_items(self):
        #print( list(self.query.items()) )
        self.assertIn(('pihole.image','pihole/image:latest'),
                      list(self.query.items()))

    def test_get(self):
        self.assertRaises( KeyError, lambda: self.query.get('non-existant'))
        self.assertEqual( self.query.get('version'), 3.0)
        self.assertEqual( self.query.get('pihole.image'), 'pihole/image:latest')
        self.assertEqual( self.query.get('pihole.environment.FOO'), 'BAR')
        self.assertEqual( self.query.get('pihole.environment.PW'), '%tag%')
        self.assertEqual( self.query.get('pihole.environment.E'), '')
        self.assertEqual( self.query.get('pihole.ports.80'), '127.0.0.1:8080')
        self.assertEqual( self.query.get('pihole.ports.53/udp'), '8053')
        self.assertEqual( self.query.get('pihole.ports.443'), '443')
        self.assertEqual( self.query.get('pihole.volumes./config'), './volumes/pihole')
        self.assertEqual( self.query.get('pihole.volumes./etc/timezone:ro'), '/etc/timezone')
        self.assertEqual( self.query.get('pihole.networks.0'), 'iotstack')

    def test_set(self):
        QUERY_LEN = len(self.query)
        self.query.set('version', 3.1)
        self.assertEqual( self.query.get('version'), 3.1)
        self.assertEqual( len(list(self.query.items())), 11)
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
        self.assertRaises(ValueError, lambda: self.query.set('service.none.existant', 0))
        self.assertEqual( len(self.query), QUERY_LEN) # no new elements

