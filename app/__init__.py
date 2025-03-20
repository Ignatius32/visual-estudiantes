from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime

# Initialize SQLAlchemy
db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    
    # Configure the SQLite database
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///students.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.urandom(24)
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')
    
    # Ensure the upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Initialize the database with the app
    db.init_app(app)
    
    with app.app_context():
        # Import routes after db initialization to avoid circular imports
        from app.routes import main, api_bp
        
        # Register blueprints
        app.register_blueprint(main)
        app.register_blueprint(api_bp)
        
        # Create database tables and initialize default data
        db.create_all()
        from app.models import Status
        Status.initialize_default_statuses()
    
    # Add template context processor for current year
    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow()}
    
    return app