"""
Integration tests for API routes

These tests verify that API endpoints respond properly
"""
import os
import pytest
from app import app as flask_app
from models import User, PointsPackage
from flask import url_for


@pytest.fixture
def app():
    """Flask application fixture"""
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    
    # Ensure we're using a test database
    test_db = os.environ.get('TEST_DATABASE_URL', 'sqlite:///test.db')
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = test_db
    
    with flask_app.app_context():
        yield flask_app


@pytest.fixture
def client(app):
    """Test client fixture"""
    return app.test_client()


def test_health_check(client):
    """Test the health check endpoint"""
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json['status'] == 'ok'
    assert 'message' in response.json


def test_points_pricing_page(client):
    """Test the points pricing page loads properly"""
    response = client.get('/points-pricing')
    assert response.status_code == 200
    assert 'text/html' in response.content_type