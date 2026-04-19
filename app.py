import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create base class for SQLAlchemy models
class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy
db = SQLAlchemy(model_class=Base)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default-dev-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Database configuration
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///inventory.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize the database
db.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# Initialize CSRF Protection
csrf = CSRFProtect(app)

# CSRF error handler
@app.errorhandler(400)
def csrf_error(error):
    from flask import render_template
    logger.error(f'CSRF Error: {error}')
    return render_template('errors/400.html', error="CSRF token validation failed. Please try again."), 400

# Import models and create tables
with app.app_context():
    from models import User, Product, Inventory, Order, OrderItem, Notification
    db.create_all()
    logger.info("Database tables created")

# Import and register filters
import filters
app.jinja_env.filters['format_category'] = filters.format_category
app.jinja_env.filters['format_gender'] = filters.format_gender
app.jinja_env.filters['product_attr'] = filters.product_attr

# Import routes
from routes import *

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))