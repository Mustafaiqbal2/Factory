from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.database import get_db
from datetime import datetime

sale_bp = Blueprint('sale', __name__)

@sale_bp.route('/')
def index():
    try:
        supabase = get_db()
        sales = supabase.table('sale').select('*').order('date', desc=True).execute().data
        return render_template('sale/index.html', sales=sales)
    except Exception as e:
        flash(f'Error loading sales: {str(e)}', 'error')
        return render_template('sale/index.html', sales=[])

@sale_bp.route('/add', methods=['GET', 'POST'])
def add():
    try:
        supabase = get_db()
        
        if request.method == 'POST':
            # Get form data
            customer_name = request.form['customer_name']
            customer_phone = request.form['customer_phone']
            stock_id = int(request.form['stock_id'])
            quantity = int(request.form['quantity'])
            rate = float(request.form['rate'])
            total = quantity * rate
            
            # Check if customer exists
            customer = supabase.table('customer').select('*').eq('name', customer_name).eq('phone', customer_phone).execute().data
            if not customer:
                flash('Customer not found. Please add the customer first.', 'error')
                return redirect(url_for('sale.add'))
            
            # Check stock availability
            stock_item = supabase.table('stock').select('*').eq('id', stock_id).execute().data
            if not stock_item:
                flash('Stock item not found.', 'error')
                return redirect(url_for('sale.add'))
            
            if stock_item[0]['quantity'] < quantity:
                flash(f'Insufficient stock. Available: {stock_item[0]["quantity"]}', 'error')
                return redirect(url_for('sale.add'))
            
            # Create sale
            sale_data = {
                'customer_name': customer_name,
                'customer_phone': customer_phone,
                'stock_id': stock_id,
                'quantity': quantity,
                'rate': rate,
                'total': total,
                'date': datetime.now().isoformat(),
                'is_refund': False
            }
            
            sale_result = supabase.table('sale').insert(sale_data).execute()
            sale_id = sale_result.data[0]['sale_id']
            
            # Update stock quantity
            new_quantity = stock_item[0]['quantity'] - quantity
            supabase.table('stock').update({'quantity': new_quantity}).eq('id', stock_id).execute()
            
            # Create transaction record
            transaction_data = {
                'customer_name': customer_name,
                'customer_phone': customer_phone,
                'amount': total,
                'type': 'sale',
                'related_sale_id': sale_id,
                'date': datetime.now().isoformat(),
                'note': f'Sale of {quantity} units at ${rate} each'
            }
            
            supabase.table('transaction').insert(transaction_data).execute()
            
            flash('Sale added successfully!', 'success')
            return redirect(url_for('sale.index'))
        
        # GET request - load data for form
        customers = supabase.table('customer').select('*').order('name').execute().data
        stock_items = supabase.table('stock').select('*').filter('quantity', 'gt', 0).order('name').execute().data
        
        # Pre-fill customer if passed in query params
        selected_customer = request.args.get('customer')
        selected_phone = request.args.get('phone')
        
        return render_template('sale/add.html', customers=customers, stock_items=stock_items,
                             selected_customer=selected_customer, selected_phone=selected_phone)
    except Exception as e:
        flash(f'Error processing sale: {str(e)}', 'error')
        return redirect(url_for('sale.index'))

@sale_bp.route('/refund/<int:sale_id>', methods=['POST'])
def refund(sale_id):
    try:
        supabase = get_db()
        
        # Get the original sale
        sale = supabase.table('sale').select('*').eq('sale_id', sale_id).execute().data
        if not sale or sale[0]['is_refund']:
            flash('Sale not found or already refunded.', 'error')
            return redirect(url_for('sale.index'))
        
        original_sale = sale[0]
        
        # Create refund record
        refund_data = {
            'customer_name': original_sale['customer_name'],
            'customer_phone': original_sale['customer_phone'],
            'stock_id': original_sale['stock_id'],
            'quantity': original_sale['quantity'],
            'rate': original_sale['rate'],
            'total': original_sale['total'],
            'date': datetime.now().isoformat(),
            'is_refund': True
        }
        
        refund_result = supabase.table('sale').insert(refund_data).execute()
        refund_id = refund_result.data[0]['sale_id']
        
        # Update stock quantity (add back)
        stock_item = supabase.table('stock').select('*').eq('id', original_sale['stock_id']).execute().data
        if stock_item:
            new_quantity = stock_item[0]['quantity'] + original_sale['quantity']
            supabase.table('stock').update({'quantity': new_quantity}).eq('id', original_sale['stock_id']).execute()
        
        # Create transaction record
        transaction_data = {
            'customer_name': original_sale['customer_name'],
            'customer_phone': original_sale['customer_phone'],
            'amount': original_sale['total'],
            'type': 'refund',
            'related_sale_id': refund_id,
            'date': datetime.now().isoformat(),
            'note': f'Refund for sale #{sale_id}'
        }
        
        supabase.table('transaction').insert(transaction_data).execute()
        
        flash('Refund processed successfully!', 'success')
    except Exception as e:
        flash(f'Error processing refund: {str(e)}', 'error')
    
    return redirect(url_for('sale.index'))

@sale_bp.route('/delete/<int:sale_id>', methods=['POST'])
def delete(sale_id):
    try:
        supabase = get_db()
        
        # Get the sale to be deleted
        sale = supabase.table('sale').select('*').eq('sale_id', sale_id).execute().data
        if not sale:
            flash('Sale not found.', 'error')
            return redirect(url_for('sale.index'))
        
        sale_data = sale[0]
        
        # If it's a regular sale (not refund), restore stock
        if not sale_data['is_refund']:
            stock_item = supabase.table('stock').select('*').eq('id', sale_data['stock_id']).execute().data
            if stock_item:
                new_quantity = stock_item[0]['quantity'] + sale_data['quantity']
                supabase.table('stock').update({'quantity': new_quantity}).eq('id', sale_data['stock_id']).execute()
        
        # Delete related transactions
        supabase.table('transaction').delete().eq('related_sale_id', sale_id).execute()
        
        # Delete the sale
        supabase.table('sale').delete().eq('sale_id', sale_id).execute()
        
        flash('Sale deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting sale: {str(e)}', 'error')
    
    return redirect(url_for('sale.index'))
