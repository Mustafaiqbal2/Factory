from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.database import get_db

stock_bp = Blueprint('stock', __name__)

@stock_bp.route('/')
def index():
    try:
        supabase = get_db()
        stock_items = supabase.table('stock').select('*').order('size').execute().data
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
            size = request.form['size']
            color = request.form['color']
            quantity = int(request.form['quantity'])
            total_cost = float(request.form['total_cost'])
            cost_per_unit = total_cost / quantity if quantity > 0 else 0
            
            # Check if this size/color combination already exists
            existing = supabase.table('stock').select('*').eq('size', size).eq('color', color).execute().data
            if existing:
                # Update existing stock by adding new quantities and costs
                existing_item = existing[0]
                new_quantity = existing_item['quantity'] + quantity
                new_total_cost = existing_item['total_cost'] + total_cost
                new_cost_per_unit = new_total_cost / new_quantity if new_quantity > 0 else 0
                
                data = {
                    'quantity': new_quantity,
                    'cost_per_unit': new_cost_per_unit,
                    'total_cost': new_total_cost
                }
                
                result = supabase.table('stock').update(data).eq('size', size).eq('color', color).execute()
                flash(f'Stock updated! New quantity: {new_quantity}, New average cost per unit: ₦{new_cost_per_unit:.2f}', 'success')
            else:
                # Create new stock item
                data = {
                    'size': size,
                    'color': color,
                    'quantity': quantity,
                    'cost_per_unit': cost_per_unit,
                    'total_cost': total_cost
                }
                
                result = supabase.table('stock').insert(data).execute()
                flash('Stock item added successfully!', 'success')
            
            return redirect(url_for('stock.index'))
        except Exception as e:
            flash(f'Error adding stock: {str(e)}', 'error')
    
    return render_template('stock/add.html')

@stock_bp.route('/edit/<size>/<color>', methods=['GET', 'POST'])
def edit(size, color):
    try:
        supabase = get_db()
        
        if request.method == 'POST':
            # Get form data
            quantity = int(request.form['quantity'])
            total_cost = float(request.form['total_cost'])
            cost_per_unit = total_cost / quantity if quantity > 0 else 0
            
            data = {
                'quantity': quantity,
                'cost_per_unit': cost_per_unit,
                'total_cost': total_cost
            }
            
            result = supabase.table('stock').update(data).eq('size', size).eq('color', color).execute()
            flash('Stock item updated successfully!', 'success')
            return redirect(url_for('stock.index'))
        
        # GET request - load stock item for editing
        stock_item = supabase.table('stock').select('*').eq('size', size).eq('color', color).execute().data
        if not stock_item:
            flash('Stock item not found!', 'error')
            return redirect(url_for('stock.index'))
        
        return render_template('stock/edit.html', stock_item=stock_item[0])
    except Exception as e:
        flash(f'Error editing stock: {str(e)}', 'error')
        return redirect(url_for('stock.index'))

@stock_bp.route('/delete/<size>/<color>', methods=['POST'])
def delete(size, color):
    try:
        supabase = get_db()
        result = supabase.table('stock').delete().eq('size', size).eq('color', color).execute()
        flash('Stock item deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting stock: {str(e)}', 'error')
    
    return redirect(url_for('stock.index'))