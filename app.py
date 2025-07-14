from flask import Flask
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv(override=True)

def create_app():
    # Specify the template and static folders relative to the app.py file
    app = Flask(__name__, 
                template_folder='app/templates',
                static_folder='app/static')
    
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Register blueprints
    from app.routes.stock import stock_bp
    from app.routes.customer import customer_bp
    from app.routes.sale import sale_bp
    from app.routes.reports import reports_bp
    from app.routes.main import main_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(stock_bp, url_prefix='/stock')
    app.register_blueprint(customer_bp, url_prefix='/customer')
    app.register_blueprint(sale_bp, url_prefix='/sale')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    
    return app

# Create the Flask application instance for Flask CLI
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)