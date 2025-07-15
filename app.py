from flask import Flask
from dotenv import load_dotenv
import os
from datetime import timedelta

# Load environment variables
load_dotenv(override=True)

def create_app():
    # Specify the template and static folders relative to the app.py file
    app = Flask(__name__, 
                template_folder='application/templates',
                static_folder='application/static')
    
    # Production-ready configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Session configuration
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)  # 24 hours
    
    # Production settings
    if os.getenv('FLASK_ENV') == 'production':
        app.config['DEBUG'] = False
        app.config['TESTING'] = False
    
    # Register blueprints
    from application.routes.auth import auth_bp
    from application.routes.stock import stock_bp
    from application.routes.customer import customer_bp
    from application.routes.sale import sale_bp
    from application.routes.payment import payment_bp
    from application.routes.reports import reports_bp
    from application.routes.main import main_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(stock_bp, url_prefix='/stock')
    app.register_blueprint(customer_bp, url_prefix='/customer')
    app.register_blueprint(sale_bp, url_prefix='/sale')
    app.register_blueprint(payment_bp, url_prefix='/payment')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    
    return app

# Create the Flask application instance
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)