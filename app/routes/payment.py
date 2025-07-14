from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.database import get_db
from datetime import datetime

payment_bp = Blueprint('payment', __name__)

@payment_bp.route('/')
def index():
    try:
        supabase = get_db()
        
        # Get search parameters
        search_customer = request.args.get('search_customer', '').strip()
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        
        # Start with base query
        query = supabase.table('payment').select('*')
        
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
        
        # Execute query with ordering
        payments = query.order('date', desc=True).execute().data
        
        return render_template('payment/index.html', payments=payments, 
                             search_customer=search_customer, 
                             start_date=start_date, 
                             end_date=end_date)
    except Exception as e:
        flash(f'Error loading payments: {str(e)}', 'error')
        return render_template('payment/index.html', payments=[])

@payment_bp.route('/add', methods=['GET', 'POST'])
def add():
    try:
        supabase = get_db()
        
        if request.method == 'POST':
            # Get form data
            customer_name = request.form['customer_name']
            customer_phone = request.form['customer_phone']
            amount = float(request.form['amount'])
            description = request.form.get('description', '')
            
            # Check if customer exists
            customer = supabase.table('customer').select('*').eq('name', customer_name).eq('phone', customer_phone).execute().data
            if not customer:
                flash('Customer not found. Please add the customer first.', 'error')
                return redirect(url_for('payment.add'))
            
            # Create payment record
            payment_data = {
                'customer_name': customer_name,
                'customer_phone': customer_phone,
                'amount': amount,
                'description': description,
                'date': datetime.now().isoformat()
            }
            
            result = supabase.table('payment').insert(payment_data).execute()
            
            # Also create a transaction record for backward compatibility
            transaction_data = {
                'customer_name': customer_name,
                'customer_phone': customer_phone,
                'amount': amount,
                'type': 'payment',
                'date': datetime.now().isoformat(),
                'note': description
            }
            
            supabase.table('transaction').insert(transaction_data).execute()
            
            flash('Payment recorded successfully!', 'success')
            return redirect(url_for('payment.index'))
        
        # GET request - load customers for form
        customers = supabase.table('customer').select('*').order('name').execute().data
        
        # Pre-fill customer if passed in query params
        selected_customer = request.args.get('customer')
        selected_phone = request.args.get('phone')
        
        return render_template('payment/add.html', customers=customers,
                             selected_customer=selected_customer, selected_phone=selected_phone)
    except Exception as e:
        flash(f'Error processing payment: {str(e)}', 'error')
        return redirect(url_for('payment.index'))

@payment_bp.route('/delete/<int:payment_id>', methods=['POST'])
def delete(payment_id):
    try:
        supabase = get_db()
        
        # Get the payment to be deleted
        payment = supabase.table('payment').select('*').eq('payment_id', payment_id).execute().data
        if not payment:
            flash('Payment not found.', 'error')
            return redirect(url_for('payment.index'))
        
        payment_data = payment[0]
        
        # Delete related transaction
        supabase.table('transaction').delete().eq('customer_name', payment_data['customer_name']).eq('customer_phone', payment_data['customer_phone']).eq('amount', payment_data['amount']).eq('type', 'payment').execute()
        
        # Delete the payment
        supabase.table('payment').delete().eq('payment_id', payment_id).execute()
        
        flash('Payment deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting payment: {str(e)}', 'error')
    
    return redirect(url_for('payment.index'))