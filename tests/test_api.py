import os,tempfile,unittest
from fastapi.testclient import TestClient
class ApiTests(unittest.TestCase):
    def test_health_and_dashboard(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ['HERMES_DATABASE_URL']=f'sqlite:///{d}/api.db'
            from cano_hermes.api.app import app
            with TestClient(app) as c:
                self.assertEqual(c.get('/api/health').status_code,200)
                self.assertIn('HERMES',c.get('/').text)
