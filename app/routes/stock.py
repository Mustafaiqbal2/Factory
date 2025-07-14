from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.database import get_db

stock_bp = Blueprint('stock', __name__)

@stock_bp.route('/')
def index():
    try:
        supabase = get_db()
        stock_items = supabase.table('stock').select('*').order('name').execute().data
        return render_template('stock/index.html', stock_items=stock_items)
    except Exception as e:
        flash(f'Error loading stock: {str(e)}', 'error')
        return render_template('stock/index.html', stock_items=[])

@stock_bp.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        try:
            supabase = get_db()
            
            # Get form data
            quantity = int(request.form['quantity'])
            unit_rate = float(request.form['unit_rate'])
            total_value = quantity * unit_rate
            
            data = {
                'name': request.form['name'],
                'size': request.form.get('size', ''),
                'color': request.form.get('color', ''),
                'quantity': quantity,
                'total_value': total_value
            }
            
            result = supabase.table('stock').insert(data).execute()
            flash('Stock item added successfully!', 'success')
            return redirect(url_for('stock.index'))
        except Exception as e:
            flash(f'Error adding stock: {str(e)}', 'error')
    
    return render_template('stock/add.html')

@stock_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    try:
        supabase = get_db()
        
        if request.method == 'POST':
            # Get form data
            quantity = int(request.form['quantity'])
            unit_rate = float(request.form['unit_rate'])
            total_value = quantity * unit_rate
            
            data = {
                'name': request.form['name'],
                'size': request.form.get('size', ''),
                'color': request.form.get('color', ''),
                'quantity': quantity,
                'total_value': total_value
            }
            
            result = supabase.table('stock').update(data).eq('id', id).execute()
            flash('Stock item updated successfully!', 'success')
            return redirect(url_for('stock.index'))
        
        # GET request - load stock item for editing
        stock_item = supabase.table('stock').select('*').eq('id', id).execute().data
        if not stock_item:
            flash('Stock item not found!', 'error')
            return redirect(url_for('stock.index'))
        
        return render_template('stock/edit.html', stock_item=stock_item[0])
    except Exception as e:
        flash(f'Error editing stock: {str(e)}', 'error')
        return redirect(url_for('stock.index'))

@stock_bp.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    try:
        supabase = get_db()
        result = supabase.table('stock').delete().eq('id', id).execute()
        flash('Stock item deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting stock: {str(e)}', 'error')
    
    return redirect(url_for('stock.index'))