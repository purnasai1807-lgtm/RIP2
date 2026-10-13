"""WSGI entrypoint (gunicorn, Railway, Docker and Vercel all use ``wsgi:app``)."""
import os

from flask import Flask
from app import create_app as _create_app


def create_app():
    try:
        return _create_app()
    except Exception as exc:  # only reached on a broken deployment
        if not os.environ.get('VERCEL'):
            raise
        # On Vercel a startup failure otherwise shows only an opaque 500. Serve a minimal
        # diagnostic page naming the problem. Only our own configuration messages (RuntimeError)
        # and import errors are shown; no values or secrets are ever printed.
        import logging
        logging.getLogger(__name__).exception('Application failed to start')
        if isinstance(exc, (RuntimeError, ImportError)):
            detail = f'{type(exc).__name__}: {exc}'
        else:
            detail = f'{type(exc).__name__} (see the Vercel function logs for the full traceback)'
        error_app = Flask('startup_error')

        @error_app.route('/', defaults={'path': ''})
        @error_app.route('/<path:path>')
        def startup_error(path):
            return (
                '<h1>CampusRipple failed to start</h1>'
                '<p>Fix the setting below in Vercel &rarr; Settings &rarr; Environment Variables, then redeploy.</p>'
                f'<pre>{detail.replace("<", "&lt;")}</pre>',
                500,
            )
        return error_app


app = create_app()
