from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.routes.auth import login_required
from app.database import get_db
from datetime import datetime

sale_bp = Blueprint('sale', __name__)

@sale_bp.route('/')
@login_required
def index():
    try:
        supabase = get_db()
        
        # Get search parameters
        search_customer = request.args.get('search_customer', '').strip()
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        
        # Start with base query
        query = supabase.table('sale').select('*')
        
        # Apply filters
        if search_customer:
            query = query.ilike('customer_name', f'%{search_customer}%')
        
        if start_date:
            query = query.gte('date', start_date)
        
        if end_date:
            # Add one day to end_date to include the full day
            end_date_plus_one = datetime.strptime(end_date, '%Y-%m-%d')
            end_date_plus_one = end_date_plus_one.replace(hour=23, minute=59, second=59)
            query = query.lte('date', end_date_plus_one.isoformat())
        
        # Execute query with ordering - Fixed order syntax
        sales = query.order('date', desc=True).execute().data
        
        return render_template('sale/index.html', sales=sales, 
                             search_customer=search_customer, 
                             start_date=start_date, 
                             end_date=end_date)
    except Exception as e:
        flash(f'Error loading sales: {str(e)}', 'error')
        return render_template('sale/index.html', sales=[])

@sale_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    try:
        supabase = get_db()
        
        if request.method == 'POST':
            # Get form data
            customer_name = request.form['customer_name']
            customer_phone = request.form['customer_phone']
            stock_size = request.form['stock_size']
            stock_color = request.form['stock_color']
            quantity = int(request.form['quantity'])
            rate = float(request.form['rate'])
            total = quantity * rate
            
            # Check if customer exists
            customer = supabase.table('customer').select('*').eq('name', customer_name).eq('phone', customer_phone).execute().data
            if not customer:
                flash('Customer not found. Please add the customer first.', 'error')
                return redirect(url_for('sale.add'))
            
            # Check stock availability (allow negative inventory)
            stock_item = supabase.table('stock').select('*').eq('size', stock_size).eq('color', stock_color).execute().data
            if not stock_item:
                flash('Stock item not found.', 'error')
                return redirect(url_for('sale.add'))
            
            current_quantity = stock_item[0]['quantity']
            new_quantity = current_quantity - quantity
            
            # Warning for negative inventory but allow the sale
            if new_quantity < 0:
                flash(f'Warning: Stock will go negative. Current: {current_quantity}, After sale: {new_quantity}', 'warning')
            
            # Calculate cost and profit
            cost_per_unit = stock_item[0]['cost_per_unit']
            total_cost = cost_per_unit * quantity
            profit = total - total_cost
            
            # Create sale
            sale_data = {
                'customer_name': customer_name,
                'customer_phone': customer_phone,
                'stock_size': stock_size,
                'stock_color': stock_color,
                'quantity': quantity,
                'rate': rate,
                'total': total,
                'cost_per_unit': cost_per_unit,
                'total_cost': total_cost,
                'profit': profit,
                'date': datetime.now().isoformat(),
                'is_refund': False
            }
            
            sale_result = supabase.table('sale').insert(sale_data).execute()
            sale_id = sale_result.data[0]['sale_id']
            
            # Update stock quantity and total cost (allow negative)
            new_total_cost = stock_item[0]['total_cost'] - total_cost
            supabase.table('stock').update({
                'quantity': new_quantity,
                'total_cost': new_total_cost
            }).eq('size', stock_size).eq('color', stock_color).execute()
            
            # Create transaction record
            transaction_data = {
                'customer_name': customer_name,
                'customer_phone': customer_phone,
                'amount': total,
                'type': 'sale',
                'related_sale_id': sale_id,
                'date': datetime.now().isoformat(),
                'note': f'Sale of {quantity} units at ₦{rate} each'
            }
            
            supabase.table('transaction').insert(transaction_data).execute()
            
            flash('Sale added successfully!', 'success')
            return redirect(url_for('sale.index'))
        
        # GET request - load data for form (show all stock items, even with 0 or negative quantity)
        customers = supabase.table('customer').select('*').order('name').execute().data
        stock_items = supabase.table('stock').select('*').order('size').execute().data
        
        # Pre-fill customer if passed in query params
        selected_customer = request.args.get('customer')
        selected_phone = request.args.get('phone')
        
        return render_template('sale/add.html', customers=customers, stock_items=stock_items,
                             selected_customer=selected_customer, selected_phone=selected_phone)
    except Exception as e:
        flash(f'Error processing sale: {str(e)}', 'error')
        return redirect(url_for('sale.index'))

@sale_bp.route('/refund/<int:sale_id>', methods=['POST'])
@login_required
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
            'stock_size': original_sale['stock_size'],
            'stock_color': original_sale['stock_color'],
            'quantity': original_sale['quantity'],
            'rate': original_sale['rate'],
            'total': original_sale['total'],
            'cost_per_unit': original_sale['cost_per_unit'],
            'total_cost': original_sale['total_cost'],
            'profit': -original_sale['profit'],  # Negative profit for refund
            'date': datetime.now().isoformat(),
            'is_refund': True
        }
        
        refund_result = supabase.table('sale').insert(refund_data).execute()
        refund_id = refund_result.data[0]['sale_id']
        
        # Update stock quantity (add back)
        stock_item = supabase.table('stock').select('*').eq('size', original_sale['stock_size']).eq('color', original_sale['stock_color']).execute().data
        if stock_item:
            new_quantity = stock_item[0]['quantity'] + original_sale['quantity']
            new_total_cost = stock_item[0]['total_cost'] + original_sale['total_cost']
            supabase.table('stock').update({
                'quantity': new_quantity,
                'total_cost': new_total_cost
            }).eq('size', original_sale['stock_size']).eq('color', original_sale['stock_color']).execute()
        
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
@login_required
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
            stock_item = supabase.table('stock').select('*').eq('size', sale_data['stock_size']).eq('color', sale_data['stock_color']).execute().data
            if stock_item:
                new_quantity = stock_item[0]['quantity'] + sale_data['quantity']
                new_total_cost = stock_item[0]['total_cost'] + sale_data['total_cost']
                supabase.table('stock').update({
                    'quantity': new_quantity,
                    'total_cost': new_total_cost
                }).eq('size', sale_data['stock_size']).eq('color', sale_data['stock_color']).execute()
        
        # Delete related transactions
        supabase.table('transaction').delete().eq('related_sale_id', sale_id).execute()
        
        # Delete the sale
        supabase.table('sale').delete().eq('sale_id', sale_id).execute()
        
        flash('Sale deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting sale: {str(e)}', 'error')
    
    return redirect(url_for('sale.index'))