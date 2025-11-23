import unittest
import json
from app import create_app, db
from models import ModuleSpec
from unittest.mock import patch

class IobuilderTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_module_lookup_from_database(self):
        # Add a test module to the database
        module = ModuleSpec(
            company='TEST_VENDOR',
            model='TEST_MODEL',
            description='A test module',
            digital_inputs=8,
            digital_outputs=8,
            verified=True
        )
        db.session.add(module)
        db.session.commit()

        response = self.client.post('/io-builder/api/module-lookup',
                                    data=json.dumps({'company': 'TEST_VENDOR', 'model': 'TEST_MODEL'}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['source'], 'database')
        self.assertEqual(data['module']['description'], 'A test module')

    def test_module_lookup_from_internal_db(self):
        response = self.client.post('/io-builder/api/module-lookup',
                                    data=json.dumps({'company': 'SIEMENS', 'model': 'SM1221'}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['source'], 'internal_db')
        self.assertEqual(data['module']['digital_inputs'], 16)

    @patch('routes.io_builder.attempt_web_lookup')
    def test_module_lookup_from_web(self, mock_web_lookup):
        # Mock the web lookup to return a valid module
        mock_web_lookup.return_value = {
            'description': 'A web-scraped module',
            'digital_inputs': 4,
            'digital_outputs': 4,
            'analog_inputs': 2,
            'analog_outputs': 2,
            'verified': False
        }

        response = self.client.post('/io-builder/api/module-lookup',
                                    data=json.dumps({'company': 'WEB_VENDOR', 'model': 'WEB_MODEL'}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['source'], 'web')
        self.assertEqual(data['module']['description'], 'A web-scraped module')

        # Verify that the module was saved to the database
        module = ModuleSpec.query.filter_by(company='WEB_VENDOR', model='WEB_MODEL').first()
        self.assertIsNotNone(module)
        self.assertEqual(module.digital_inputs, 4)

    def test_module_lookup_not_found(self):
        response = self.client.post('/io-builder/api/module-lookup',
                                    data=json.dumps({'company': 'UNKNOWN_VENDOR', 'model': 'UNKNOWN_MODEL'}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('not found', data['message'])

    def test_generate_io_table(self):
        modules = [
            {
                'company': 'TEST_VENDOR',
                'model': 'TEST_MODEL_DI',
                'digital_inputs': 8
            },
            {
                'company': 'TEST_VENDOR',
                'model': 'TEST_MODEL_DO',
                'digital_outputs': 4
            }
        ]
        response = self.client.post('/io-builder/api/generate-io-table',
                                    data=json.dumps({'modules': modules}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['tables']['digital_inputs']), 8)
        self.assertEqual(len(data['tables']['digital_outputs']), 4)
        self.assertEqual(data['summary']['total_points'], 12)

if __name__ == '__main__':
    unittest.main()
