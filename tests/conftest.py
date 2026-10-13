"""Shared pytest fixtures for tests outside test_app.py.

Keep the lightweight SQLite setup consistent across the incident, evidence,
impact and authorization suites. Individual test modules may override these
fixtures when they need a specialized configuration.
"""
import pytest
from app import create_app, db


@pytest.fixture()
def app():
    application = create_app({
        'TESTING': True,
        'SECRET_KEY': 'test-secret-key-that-is-long-enough-for-tests',
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
        'SESSION_COOKIE_SECURE': False,
        'HEALTHCHECK_DATABASE': False,
    })
    with application.app_context():
        # Import models before creating the test schema.
        from app import models  # noqa: F401
        db.drop_all()
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
