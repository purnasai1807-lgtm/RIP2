from scripts.preflight import check_configuration


def test_production_preflight_rejects_placeholder_configuration():
    errors, _warnings = check_configuration({
        'APP_ENV': 'production',
        'SECRET_KEY': 'replace-with-a-long-random-secret-value-123456789',
        'DATABASE_URL': 'sqlite:///local.db',
        'COOKIE_SECURE': 'false',
        'REQUIRE_EMAIL_VERIFICATION': 'true',
        'MAIL_SERVER': 'smtp.example.com',
        'MAIL_DEFAULT_SENDER': 'no-reply@example.com',
        'MAIL_PASSWORD': 'example-password',
        'PUBLIC_BASE_URL': 'https://your-campusripple-domain.example',
        'INSTITUTIONAL_EMAIL_DOMAINS': 'gmail.com',
    })
    assert len(errors) >= 5
    assert any('SECRET_KEY' in error for error in errors)
    assert any('PostgreSQL' in error for error in errors)
    assert any('COOKIE_SECURE' in error for error in errors)


def test_production_preflight_accepts_complete_shape_of_configuration():
    errors, warnings = check_configuration({
        'APP_ENV': 'production',
        'SECRET_KEY': 'a' * 48,
        'DATABASE_URL': 'postgresql+psycopg://app:strongpassword@db.internal:5432/campusripple',
        'COOKIE_SECURE': 'true',
        'REQUIRE_EMAIL_VERIFICATION': 'true',
        'MAIL_SERVER': 'smtp.mailprovider.net',
        'MAIL_DEFAULT_SENDER': 'CampusRipple <no-reply@college.edu>',
        'MAIL_PASSWORD': 'a-realistic-secret-value',
        'PUBLIC_BASE_URL': 'https://campusripple.college.edu',
        'INSTITUTIONAL_EMAIL_DOMAINS': 'aceec.ac.in',
    })
    assert errors == []
    assert any('API is not configured' in warning for warning in warnings)


def test_preflight_rejects_incomplete_official_api_pair():
    errors, _warnings = check_configuration({
        'APP_ENV': 'development',
        'COLLEGE_DATA_API_URL': 'https://api.college.edu/timetable',
        'COLLEGE_DATA_API_TOKEN': '',
    })
    assert any('must either both be set' in error for error in errors)


def test_production_preflight_rejects_wrong_email_domain_even_without_verification():
    errors, _warnings = check_configuration({
        'APP_ENV': 'production',
        'SECRET_KEY': 'a' * 48,
        'DATABASE_URL': 'postgresql+psycopg://app:strongpassword@db.internal:5432/campusripple',
        'COOKIE_SECURE': 'true',
        'REQUIRE_EMAIL_VERIFICATION': 'false',
        'INSTITUTIONAL_EMAIL_DOMAINS': 'aceec.ac.in,gmail.com',
    })
    assert any('must be exactly aceec.ac.in' in error for error in errors)
