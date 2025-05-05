"""
Unit tests for database connection

These tests verify that the database connection is working correctly
"""
import pytest
from app import app, db
from sqlalchemy.exc import SQLAlchemyError


@pytest.fixture
def test_app():
    """Flask application fixture"""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    with app.app_context():
        yield app


def test_db_connection(test_app):
    """Test database connection is working"""
    try:
        # Try to execute a simple query
        result = db.session.execute("SELECT 1").fetchone()
        assert result[0] == 1
    except SQLAlchemyError as e:
        pytest.fail(f"Database connection failed: {str(e)}")


def test_create_test_tables(test_app):
    """Test database tables can be created"""
    try:
        # Import models to ensure they're registered with SQLAlchemy
        from models import User, PointsPackage
        
        # Only create tables in memory for test
        db.create_all()
        assert True  # If we get here without error, the test passed
    except SQLAlchemyError as e:
        pytest.fail(f"Failed to create database tables: {str(e)}")