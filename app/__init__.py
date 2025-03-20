from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os
from datetime import datetime

# Initialize SQLAlchemy
db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    
    # Configure the SQLite database
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///students.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.urandom(24)
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')
    
    # File upload configurations
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
    app.config['UPLOAD_EXTENSIONS'] = ['.xlsx', '.xls']
    app.config['MAX_UPLOAD_TIME'] = 300  # 5 minutes timeout
    
    # Ensure the upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Initialize the database with the app
    db.init_app(app)
    
    # Initialize login manager
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    login_manager.login_message = 'Por favor inicie sesión para acceder a esta página.'
    
    @login_manager.user_loader
    def load_user(id):
        from app.models import User
        return User.query.get(int(id))
    
    with app.app_context():
        # Import routes after db initialization to avoid circular imports
        from app.routes import main, api_bp
        
        # Register blueprints
        app.register_blueprint(main)
        app.register_blueprint(api_bp)
        
        # Create database tables and initialize default data
        db.create_all()
        from app.models import Status, User
        Status.initialize_default_statuses()
        User.initialize_default_admin()
    
    # Add template context processor for current year
    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow()}
    
    return app