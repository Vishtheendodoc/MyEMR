"""User account helpers and lightweight SQLite migrations."""

from sqlalchemy import inspect, text

from models import db, User


def ensure_user_columns():
    """Add email/display_name columns and backfill legacy accounts."""
    inspector = inspect(db.engine)
    if 'user' not in inspector.get_table_names():
        return

    columns = {column['name'] for column in inspector.get_columns('user')}
    statements = []
    if 'email' not in columns:
        statements.append('ALTER TABLE user ADD COLUMN email VARCHAR(200)')
    if 'display_name' not in columns:
        statements.append('ALTER TABLE user ADD COLUMN display_name VARCHAR(150)')

    with db.engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))

    changed = False
    for user in User.query.all():
        if not user.display_name:
            user.display_name = user.username
            changed = True
        if not user.email:
            base = (user.username or f'user{user.id}').strip().lower().replace(' ', '.')
            candidate = base if '@' in base else f'{base}@legacy.emr'
            if User.query.filter(User.email == candidate, User.id != user.id).first():
                candidate = f'user{user.id}@legacy.emr'
            user.email = candidate
            changed = True

    if changed:
        db.session.commit()


def normalize_email(value):
    return (value or '').strip().lower()


def find_user_by_login(login_value):
    """Find a user by email (preferred) or legacy username."""
    login_value = (login_value or '').strip()
    if not login_value:
        return None

    email = normalize_email(login_value)
    user = User.query.filter(db.func.lower(User.email) == email).first()
    if user:
        return user

    return User.query.filter(User.username.ilike(login_value)).first()


def email_exists(email):
    normalized = normalize_email(email)
    return User.query.filter(db.func.lower(User.email) == normalized).first() is not None
