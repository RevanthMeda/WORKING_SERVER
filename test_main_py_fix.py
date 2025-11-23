import unittest
import json
from app import create_app, db
from models import Report, SATReport, User
from unittest.mock import patch, MagicMock
import os

class MainPyFixTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

        # Create a mock user and log them in
        self.user = User(email='test@example.com', role='Engineer', full_name='Test User')
        self.user.set_password('password')
        db.session.add(self.user)
        db.session.commit()
        self.client.post('/login', data={'email': 'test@example.com', 'password': 'password'})

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_save_progress_with_image_urls(self):
        # Simulate a POST request to save_progress with some data
        with patch('routes.main.handle_image_removals'), \
             patch('routes.main.save_uploaded_images'):
            
            response = self.client.post('/save_progress', data={
                'submission_id': '',
                'document_title': 'Test Report',
                'scada_image_urls': json.dumps(['/static/uploads/test/test.jpg'])
            })

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertTrue(data['success'])
            self.assertEqual(data['message'], 'Progress saved successfully')

            # Verify that the SATReport was created with the correct image URLs
            sat_report = SATReport.query.first()
            self.assertIsNotNone(sat_report)
            scada_urls = json.loads(sat_report.scada_image_urls)
            self.assertEqual(scada_urls, ['/static/uploads/test/test.jpg'])

if __name__ == '__main__':
    unittest.main()
