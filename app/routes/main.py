from flask import Blueprint, render_template
from app.database import get_db

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    try:
        supabase = get_db()
        
        # Get dashboard statistics
        stock_count = len(supabase.table('stock').select('*').execute().data)
        customer_count = len(supabase.table('customer').select('*').execute().data)
        
        # Get recent sales (last 5)
        recent_sales = supabase.table('sale').select('*').order('date', desc=True).limit(5).execute().data
        
        # Get low stock items (quantity <= 5)
        low_stock = supabase.table('stock').select('*').filter('quantity', 'lte', 5).execute().data
        
        # Calculate total inventory value using new schema
        stock_items = supabase.table('stock').select('*').execute().data
        total_inventory_value = sum(item.get('total_cost', 0) for item in stock_items)
        
        stats = {
            'stock_count': stock_count,
            'customer_count': customer_count,
            'recent_sales': recent_sales,
            'low_stock': low_stock,
            'total_inventory_value': total_inventory_value
        }
        
        return render_template('dashboard.html', stats=stats)
    except Exception as e:
        return render_template('dashboard.html', stats={
            'stock_count': 0,
            'customer_count': 0,
            'recent_sales': [],
            'low_stock': [],
            'total_inventory_value': 0
        }, error=str(e))