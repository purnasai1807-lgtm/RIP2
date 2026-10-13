"""Staging-only CampusRipple load profile. Use synthetic test accounts and data."""
import re
from locust import HttpUser, task, between

class CampusRippleUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Provide LOAD_TEST_EMAIL and LOAD_TEST_PASSWORD in the shell environment.
        import os
        self.email = os.environ.get('LOAD_TEST_EMAIL', '')
        self.password = os.environ.get('LOAD_TEST_PASSWORD', '')
        response = self.client.get('/login', name='GET /login')
        match = re.search(r'name="_csrf_token" value="([^"]+)"', response.text)
        if not self.email or not self.password or not match:
            return
        self.client.post('/login', name='POST /login', data={
            '_csrf_token': match.group(1), 'email': self.email, 'password': self.password
        }, allow_redirects=True)

    @task(5)
    def browse_workspace(self):
        self.client.get('/college-workspace', name='GET /college-workspace')

    @task(4)
    def browse_dashboard(self):
        self.client.get('/dashboard', name='GET /dashboard')

    @task(3)
    def browse_decision_form(self):
        self.client.get('/scenarios/new', name='GET /scenarios/new')

    @task(1)
    def health_check(self):
        self.client.get('/livez', name='GET /livez')
        self.client.get('/healthz', name='GET /healthz')
