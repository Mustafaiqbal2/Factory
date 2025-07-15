from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.routes.auth import login_required
from app.database import get_db

customer_bp = Blueprint('customer', __name__)

@customer_bp.route('/')
@login_required
def index():
    try:
        supabase = get_db()
        
        # Get search parameter
        search_query = request.args.get('search', '').strip()
        
        # Start with base query
        query = supabase.table('customer').select('*')
        
        # Apply search filter if provided
        if search_query:
            query = query.or_(f'name.ilike.%{search_query}%,phone.ilike.%{search_query}%,company.ilike.%{search_query}%')
        
        # Execute query with ordering
        customers = query.order('name').execute().data
        
        return render_template('customer/index.html', customers=customers, search_query=search_query)
    except Exception as e:
        flash(f'Error loading customers: {str(e)}', 'error')
        return render_template('customer/index.html', customers=[], search_query='')

@customer_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    if request.method == 'POST':
        try:
            supabase = get_db()
            data = {
                'name': request.form['name'],
                'phone': request.form['phone'],
                'company': request.form.get('company', '')
            }
            
            result = supabase.table('customer').insert(data).execute()
            flash('Customer added successfully!', 'success')
            return redirect(url_for('customer.index'))
        except Exception as e:
            flash(f'Error adding customer: {str(e)}', 'error')
    
    return render_template('customer/add.html')

@customer_bp.route('/edit/<name>/<phone>', methods=['GET', 'POST'])
@login_required
def edit(name, phone):
    try:
        supabase = get_db()
        
        if request.method == 'POST':
            data = {
                'company': request.form.get('company', '')
            }
            
            # Update customer (name and phone are primary keys, so they can't be changed)
            result = supabase.table('customer').update(data).eq('name', name).eq('phone', phone).execute()
            flash('Customer updated successfully!', 'success')
            return redirect(url_for('customer.index'))
        
        # GET request - load customer for editing
        customer = supabase.table('customer').select('*').eq('name', name).eq('phone', phone).execute().data
        if not customer:
            flash('Customer not found!', 'error')
            return redirect(url_for('customer.index'))
        
        return render_template('customer/edit.html', customer=customer[0])
    except Exception as e:
        flash(f'Error editing customer: {str(e)}', 'error')
        return redirect(url_for('customer.index'))

@customer_bp.route('/delete/<name>/<phone>', methods=['POST'])
@login_required
def delete(name, phone):
    try:
        supabase = get_db()
        result = supabase.table('customer').delete().eq('name', name).eq('phone', phone).execute()
        flash('Customer deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting customer: {str(e)}', 'error')
    
    return redirect(url_for('customer.index'))

@customer_bp.route('/view/<name>/<phone>')
@login_required
def view(name, phone):
    try:
        supabase = get_db()
        
        # Get customer details
        customer = supabase.table('customer').select('*').eq('name', name).eq('phone', phone).execute().data
        if not customer:
            flash('Customer not found!', 'error')
            return redirect(url_for('customer.index'))
        
        # Get customer's sales
        sales = supabase.table('sale').select('*').eq('customer_name', name).eq('customer_phone', phone).order('date', desc=True).execute().data
        
        # Get customer's transactions
        transactions = supabase.table('transaction').select('*').eq('customer_name', name).eq('customer_phone', phone).order('date', desc=True).execute().data
        
        # Calculate balance
        total_sales = sum(sale['total'] for sale in sales if not sale['is_refund'])
        total_refunds = sum(sale['total'] for sale in sales if sale['is_refund'])
        total_payments = sum(t['amount'] for t in transactions if t['type'] == 'payment')
        total_advances = sum(t['amount'] for t in transactions if t['type'] == 'advance')
        
        balance = total_sales - total_refunds - total_payments + total_advances
        
        return render_template('customer/view.html', 
                             customer=customer[0], 
                             sales=sales, 
                             transactions=transactions,
                             balance=balance)
    except Exception as e:
        flash(f'Error loading customer details: {str(e)}', 'error')
        return redirect(url_for('customer.index'))