import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import inspect, text
from flask_login import LoginManager
import click

# Flask-Login is provided by Flask's standard ecosystem dependency below.
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth_login"
login_manager.login_message_category = "info"


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    database_url = os.environ.get("DATABASE_URL", "sqlite:///decision_impact.db")
    if database_url.startswith('postgres://'):
        database_url = 'postgresql+psycopg://' + database_url[len('postgres://'):]
    elif database_url.startswith('postgresql://'):
        database_url = 'postgresql+psycopg://' + database_url[len('postgresql://'):]
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-this-secret"),
        APP_ENV=os.environ.get('APP_ENV', 'development').lower(),
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "true" if os.environ.get('VERCEL') else "false").lower() == "true",
        TRUST_PROXY_HEADERS=os.environ.get('TRUST_PROXY_HEADERS', 'false').lower() == 'true',
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        PASSWORD_RESET_MIN_INTERVAL=60,
        MAIL_SERVER=os.environ.get('MAIL_SERVER', ''),
        MAIL_PORT=int(os.environ.get('MAIL_PORT', '587')),
        MAIL_USE_TLS=os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true',
        MAIL_USE_SSL=os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true',
        MAIL_USERNAME=os.environ.get('MAIL_USERNAME', ''),
        MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD', ''),
        MAIL_DEFAULT_SENDER=os.environ.get('MAIL_DEFAULT_SENDER', ''),
        PUBLIC_BASE_URL=os.environ.get('PUBLIC_BASE_URL') or (('https://' + os.environ['VERCEL_PROJECT_PRODUCTION_URL']) if os.environ.get('VERCEL_PROJECT_PRODUCTION_URL') else 'http://127.0.0.1:5000'),
        REQUIRE_EMAIL_VERIFICATION=os.environ.get('REQUIRE_EMAIL_VERIFICATION', 'true' if os.environ.get('APP_ENV', 'development').lower() == 'production' else 'false').lower() == 'true',
        INSTITUTIONAL_EMAIL_DOMAINS=tuple(domain.strip().lower().lstrip('@') for domain in os.environ.get('INSTITUTIONAL_EMAIL_DOMAINS', '').split(',') if domain.strip()),
        COLLEGE_DATA_API_URL=os.environ.get('COLLEGE_DATA_API_URL', ''),
        COLLEGE_DATA_API_TOKEN=os.environ.get('COLLEGE_DATA_API_TOKEN', ''),
        COLLEGE_DATA_API_TIMEOUT=int(os.environ.get('COLLEGE_DATA_API_TIMEOUT', '15')),
        COLLEGE_DATA_ALLOW_EMPTY_SYNC=os.environ.get('COLLEGE_DATA_ALLOW_EMPTY_SYNC', 'false').lower() == 'true',
        HEALTHCHECK_DATABASE=True,
        SKIP_AUTO_SCHEMA=os.environ.get('SKIP_AUTO_SCHEMA', 'false').lower() == 'true',
    )
    if os.environ.get('VERCEL'):
        # Serverless: every invocation may be a fresh process, so don't hold local pools open and
        # stay compatible with transaction poolers (Neon/Supabase/PgBouncer) that reject prepared statements.
        from sqlalchemy.pool import NullPool
        engine_options = {'poolclass': NullPool}
        if database_url.startswith('postgresql+psycopg'):
            engine_options['connect_args'] = {'prepare_threshold': None}
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options
        app.config.setdefault('TRUST_PROXY_HEADERS', True)
    if test_config:
        app.config.update(test_config)
    # Eligibility policy: only ACE Engineering College email accounts are allowed.
    # This is intentionally not configurable through environment variables.
    app.config['INSTITUTIONAL_EMAIL_DOMAINS'] = ('aceec.ac.in',)
    if app.config.get('APP_ENV') == 'production':
        secret = app.config.get('SECRET_KEY', '')
        if (not secret or secret == 'dev-only-change-this-secret' or len(secret) < 32 or
                'replace-with' in secret.lower() or 'change_me' in secret.lower()):
            raise RuntimeError('Production requires a unique, non-placeholder SECRET_KEY of at least 32 characters.')
        if not str(app.config.get('SQLALCHEMY_DATABASE_URI', '')).startswith('postgresql+'):
            raise RuntimeError('Production requires PostgreSQL; SQLite is only for local development and lightweight tests.')
        if not app.config.get('SESSION_COOKIE_SECURE'):
            raise RuntimeError('Production requires COOKIE_SECURE=true and HTTPS at the public endpoint.')
        if app.config.get('REQUIRE_EMAIL_VERIFICATION') and not (app.config.get('MAIL_SERVER') and app.config.get('MAIL_DEFAULT_SENDER')):
            raise RuntimeError('Production email verification requires MAIL_SERVER and MAIL_DEFAULT_SENDER.')
        if app.config.get('REQUIRE_EMAIL_VERIFICATION') and ('.example' in str(app.config.get('MAIL_SERVER', '')).lower() or '@example.com' in str(app.config.get('MAIL_DEFAULT_SENDER', '')).lower()):
            raise RuntimeError('Replace example SMTP settings with a real provider configuration before production.')
        public_url = str(app.config.get('PUBLIC_BASE_URL', '')).lower()
        if app.config.get('REQUIRE_EMAIL_VERIFICATION') and (not public_url.startswith('https://') or '.example' in public_url or 'localhost' in public_url):
            raise RuntimeError('Production email verification requires PUBLIC_BASE_URL to use your real HTTPS domain.')
        domains = app.config.get('INSTITUTIONAL_EMAIL_DOMAINS', ())
        if app.config.get('REQUIRE_EMAIL_VERIFICATION') and (not domains or any('replace-with-approved' in domain for domain in domains)):
            raise RuntimeError('Production email verification requires the institution-approved INSTITUTIONAL_EMAIL_DOMAINS allowlist.')
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        # Read-only filesystems (e.g. Vercel serverless) cannot create the instance folder.
        # It is only needed for local SQLite; production uses PostgreSQL.
        pass
    db.init_app(app)
    migrate.init_app(app, db, compare_type=True)
    login_manager.init_app(app)

    @app.after_request
    def apply_security_headers(response):
        """Apply baseline browser security headers without breaking inline assets."""
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        response.headers.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        response.headers.setdefault('Cross-Origin-Resource-Policy', 'same-origin')
        if app.config.get('SESSION_COOKIE_SECURE') or app.config.get('APP_ENV') == 'production':
            response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
        return response

    @app.cli.command('create-admin')
    @click.argument('email')
    def create_admin_command(email):
        """Create or promote an administrator from a trusted server shell."""
        from .models import User
        normalized_email = email.strip().lower()
        from .routes import is_eligible_college_email
        if len(normalized_email) > 254 or not is_eligible_college_email(normalized_email):
            raise click.ClickException('Administrator accounts must use an eligible @aceec.ac.in email address.')
        with app.app_context():
            user = User.query.filter_by(email=normalized_email).first()
            if user is None:
                name = click.prompt('Administrator display name', default='CampusRipple Admin')
                password = click.prompt('Initial password (minimum 12 characters)', hide_input=True, confirmation_prompt=True)
                if len(password) < 12:
                    raise click.ClickException('Password must contain at least 12 characters.')
                user = User(email=normalized_email, name=name.strip()[:80] or 'CampusRipple Admin')
                user.set_password(password)
                user.role = 'admin'
                from .models import utcnow
                user.email_verified_at = utcnow()
                db.session.add(user)
            else:
                user.role = 'admin'
                if user.email_verified_at is None:
                    from .models import utcnow
                    user.email_verified_at = utcnow()
            db.session.commit()
            click.echo(f'Administrator role configured for {normalized_email}.')

    @app.cli.command('seed-demo-data')
    def seed_demo_data_command():
        """Deprecated safety guard: this project does not generate fictional college records."""
        raise click.ClickException(
            'Synthetic college-data seeding is disabled. Import only authorized real institutional records '
            'through the approved import/integration workflow. No records were created.'
        )

    @app.cli.command('test-mail')
    @click.argument('recipient')
    def test_mail_command(recipient):
        """Send a non-secret SMTP configuration test to a controlled mailbox."""
        from .routes import send_smtp_test_email
        delivered = send_smtp_test_email(app, recipient)
        if not delivered:
            raise click.ClickException('SMTP test failed. Check MAIL_SERVER, MAIL_PORT, MAIL_USE_TLS, MAIL_USERNAME, MAIL_PASSWORD and MAIL_DEFAULT_SENDER.')
        click.echo('SMTP test email sent. Check the recipient mailbox and spam folder.')

    @app.cli.command('sync-official-timetable')
    @click.option('--confirm', is_flag=True, help='Required to run the configured official timetable synchronization.')
    def sync_official_timetable_command(confirm):
        """Fetch an institution-approved read-only timetable API and reconcile local records."""
        if not confirm:
            raise click.ClickException('Review the source contract and run with --confirm to proceed.')
        from .integrations.sync import sync_official_timetable
        with app.app_context():
            try:
                result = sync_official_timetable(app)
            except Exception as exc:
                raise click.ClickException(str(exc)) from exc
        click.echo(f"Sync complete: received={result['received']} created={result['created']} updated={result['updated']} status={result['status']}")

    from .models import User, Scenario, Impact

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from .routes import register_routes
    register_routes(app)

    # Schema creation is intentionally restricted to tests and local development. Production
    # schema changes must be applied explicitly with `flask --app wsgi:app db upgrade`.
    if app.config.get('TESTING') or (app.config.get('APP_ENV') != 'production' and not app.config.get('SKIP_AUTO_SCHEMA')):
        with app.app_context():
            db.create_all()
            inspector = inspect(db.engine)
            user_columns = {column['name'] for column in inspector.get_columns('user')}
            timetable_columns = {column['name'] for column in inspector.get_columns('timetable_entry')}
            scenario_columns = {column['name'] for column in inspector.get_columns('scenario')}
            impact_columns = {column['name'] for column in inspector.get_columns('impact')}
            with db.engine.begin() as connection:
                user_additions = {
                    'reset_token_hash': 'VARCHAR(64)',
                    'reset_token_expires_at': 'TIMESTAMP',
                    'email_verified_at': 'TIMESTAMP',
                    'email_verification_token_hash': 'VARCHAR(64)',
                    'email_verification_expires_at': 'TIMESTAMP',
                }
                for column, sql_type in user_additions.items():
                    if column not in user_columns:
                        connection.execute(text(f'ALTER TABLE "user" ADD COLUMN {column} {sql_type}'))
                timetable_additions = {
                    'source_system': "VARCHAR(40) NOT NULL DEFAULT 'manual'",
                    'source_record_id': 'VARCHAR(100)',
                    'source_synced_at': 'TIMESTAMP',
                }
                for column, sql_type in timetable_additions.items():
                    if column not in timetable_columns:
                        connection.execute(text(f'ALTER TABLE timetable_entry ADD COLUMN {column} {sql_type}'))
                for column, sql_type in {'analysis_version': 'VARCHAR(40)', 'analyzed_at': 'TIMESTAMP'}.items():
                    if column not in scenario_columns:
                        connection.execute(text(f'ALTER TABLE scenario ADD COLUMN {column} {sql_type}'))
                if 'evidence_ref' not in impact_columns:
                    connection.execute(text('ALTER TABLE impact ADD COLUMN evidence_ref VARCHAR(160)'))
                connection.execute(text('CREATE INDEX IF NOT EXISTS ix_user_email_verification_token_hash ON "user" (email_verification_token_hash)'))
                connection.execute(text('CREATE INDEX IF NOT EXISTS ix_timetable_entry_source_record_id ON timetable_entry (source_record_id)'))
    return app
