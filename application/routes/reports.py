from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
from application.routes.auth import login_required
from application.database import get_db
from playwright.sync_api import sync_playwright
from datetime import datetime
import json


reports_bp = Blueprint('reports', __name__)

def html_to_pdf(html_content, filename):
    """Convert HTML to PDF using Playwright - works in production"""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_content)
        
        # Wait for any dynamic content to load
        page.wait_for_timeout(2000)
        
        # Generate PDF with proper options
        pdf_bytes = page.pdf(
            format='A4',
            margin={
                'top': '1cm',
                'right': '1cm', 
                'bottom': '1cm',
                'left': '1cm'
            },
            print_background=True,
            prefer_css_page_size=True
        )
        
        browser.close()
        return pdf_bytes

@reports_bp.route('/')
@login_required
def index():
    return render_template('reports/index.html')

@reports_bp.route('/account')
@login_required
def account_report():
    try:
        supabase = get_db()
        customers = supabase.table('customer').select('*').order('name').execute().data
        
        selected_customer = request.args.get('customer')
        selected_phone = request.args.get('phone')
        
        account_data = None
        if selected_customer and selected_phone:
            # Get customer's sales
            sales = supabase.table('sale').select('*').eq('customer_name', selected_customer).eq('customer_phone', selected_phone).order('date', desc=True).execute().data
            
            # Get customer's payments
            payments = supabase.table('payment').select('*').eq('customer_name', selected_customer).eq('customer_phone', selected_phone).order('date', desc=True).execute().data
            
            # Get customer's transactions
            transactions = supabase.table('transaction').select('*').eq('customer_name', selected_customer).eq('customer_phone', selected_phone).order('date', desc=True).execute().data
            
            # Calculate balance
            total_sales = sum(sale['total'] for sale in sales if not sale['is_refund'])
            total_refunds = sum(sale['total'] for sale in sales if sale['is_refund'])
            total_payments = sum(payment['amount'] for payment in payments)
            total_advances = sum(t['amount'] for t in transactions if t['type'] == 'advance')
            
            balance = total_sales - total_refunds - total_payments + total_advances
            
            account_data = {
                'customer_name': selected_customer,
                'customer_phone': selected_phone,
                'sales': sales,
                'payments': payments,
                'transactions': transactions,
                'total_sales': total_sales,
                'total_refunds': total_refunds,
                'total_payments': total_payments,
                'total_advances': total_advances,
                'balance': balance
            }
        
        return render_template('reports/account.html', customers=customers, account_data=account_data)
    except Exception as e:
        flash(f'Error generating account report: {str(e)}', 'error')
        return render_template('reports/account.html', customers=[], account_data=None)

@reports_bp.route('/sales_by_stock')
@login_required
def sales_by_stock():
    try:
        supabase = get_db()
        
        # Get grouping preference
        group_by = request.args.get('group_by', 'item')  # 'item', 'size', 'color'
        
        # Get all sales with stock information
        sales = supabase.table('sale').select('*').execute().data
        stock_items = supabase.table('stock').select('*').execute().data
        
        # Create stock lookup using size and color as key
        stock_lookup = {f"{item['size']}_{item['color']}": item for item in stock_items}
        
        # Group sales by stock based on preference
        stock_sales = {}
        
        for sale in sales:
            if group_by == 'size':
                group_key = sale['stock_size']
                group_name = sale['stock_size']
            elif group_by == 'color':
                group_key = sale['stock_color']
                group_name = sale['stock_color']
            else:  # group by item (size + color)
                group_key = f"{sale['stock_size']}_{sale['stock_color']}"
                group_name = f"{sale['stock_size']} - {sale['stock_color']}"
            
            if group_key not in stock_sales:
                stock_sales[group_key] = {
                    'group_name': group_name,
                    'stock_item': stock_lookup.get(f"{sale['stock_size']}_{sale['stock_color']}", 
                                                 {'size': sale['stock_size'], 'color': sale['stock_color']}),
                    'total_quantity_sold': 0,
                    'total_quantity_refunded': 0,
                    'total_sales_amount': 0,
                    'total_refund_amount': 0,
                    'sales_count': 0,
                    'refund_count': 0
                }
            
            if sale['is_refund']:
                stock_sales[group_key]['total_quantity_refunded'] += sale['quantity']
                stock_sales[group_key]['total_refund_amount'] += sale['total']
                stock_sales[group_key]['refund_count'] += 1
            else:
                stock_sales[group_key]['total_quantity_sold'] += sale['quantity']
                stock_sales[group_key]['total_sales_amount'] += sale['total']
                stock_sales[group_key]['sales_count'] += 1
        
        # Sort by net revenue (descending)
        stock_sales = dict(sorted(stock_sales.items(), 
                                key=lambda x: x[1]['total_sales_amount'] - x[1]['total_refund_amount'], 
                                reverse=True))
        
        # ENHANCED COLORFUL CHART DATA
        chart_labels = []
        chart_values = []
        chart_colors = []
        
        if stock_sales:
            # Enhanced color maps with more vibrant colors
            color_map = {
                'Red': '#FF4757', 'Blue': '#3742FA', 'Black': '#2F3542', 
                'White': '#A4B0BE', 'Green': '#2ED573', 'Yellow': '#FFA502',
                'Purple': '#8E44AD', 'Orange': '#FF6348', 'Pink': '#FF3838',
                'Brown': '#8B4513', 'Grey': '#57606F', 'Gray': '#57606F'
            }
            
            # Vibrant palette for items/sizes
            vibrant_palette = [
                '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57',
                '#FF9FF3', '#54A0FF', '#5F27CD', '#00D2D3', '#FF9F43',
                '#EE5A24', '#009432', '#0652DD', '#9980FA', '#FFC312',
                '#C4E538', '#12CBC4', '#FDA7DF', '#ED4C67', '#F79F1F'
            ]
            
            # ENSURE ONLY PRIMITIVE DATA TYPES
            color_index = 0
            for key, data in stock_sales.items():
                net_revenue = float(data['total_sales_amount'] - data['total_refund_amount'])
                chart_labels.append(str(data['group_name']))
                chart_values.append(net_revenue)
                
                # Set color based on group type
                if group_by == 'color':
                    chart_colors.append(color_map.get(str(data['group_name']), '#6c757d'))
                else:
                    # Use vibrant palette for items and sizes
                    chart_colors.append(vibrant_palette[color_index % len(vibrant_palette)])
                    color_index += 1
        
        # PASS JSON STRINGS DIRECTLY
        chart_data = {
            'labels_json': json.dumps(chart_labels),
            'values_json': json.dumps(chart_values),
            'colors_json': json.dumps(chart_colors)
        }
        
        return render_template('reports/sales_by_stock.html', 
                             stock_sales=stock_sales, 
                             group_by=group_by,
                             chart_data=chart_data)
    except Exception as e:
        print(f"ERROR in sales_by_stock: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Error generating sales by stock report: {str(e)}', 'error')
        return render_template('reports/sales_by_stock.html', 
                             stock_sales={}, 
                             group_by='item', 
                             chart_data={
                                 'labels_json': json.dumps([]),
                                 'values_json': json.dumps([]),
                                 'colors_json': json.dumps([])
                             })

@reports_bp.route('/sales_by_customer')
@login_required
def sales_by_customer():
    try:
        supabase = get_db()
        
        # Get sorting preference
        sort_by = request.args.get('sort_by', 'revenue')  # 'revenue', 'quantity', 'transactions'
        
        # Get all sales and payments
        sales = supabase.table('sale').select('*').execute().data
        payments = supabase.table('payment').select('*').execute().data
        
        # Group sales by customer
        customer_sales = {}
        for sale in sales:
            customer_key = f"{sale['customer_name']}|{sale['customer_phone']}"
            if customer_key not in customer_sales:
                customer_sales[customer_key] = {
                    'customer_name': sale['customer_name'],
                    'customer_phone': sale['customer_phone'],
                    'total_quantity_sold': 0,
                    'total_quantity_refunded': 0,
                    'total_sales_amount': 0,
                    'total_refund_amount': 0,
                    'total_payments': 0,
                    'sales_count': 0,
                    'refund_count': 0
                }
            
            if sale['is_refund']:
                customer_sales[customer_key]['total_quantity_refunded'] += sale['quantity']
                customer_sales[customer_key]['total_refund_amount'] += sale['total']
                customer_sales[customer_key]['refund_count'] += 1
            else:
                customer_sales[customer_key]['total_quantity_sold'] += sale['quantity']
                customer_sales[customer_key]['total_sales_amount'] += sale['total']
                customer_sales[customer_key]['sales_count'] += 1
        
        # Add payment data
        for payment in payments:
            customer_key = f"{payment['customer_name']}|{payment['customer_phone']}"
            if customer_key in customer_sales:
                customer_sales[customer_key]['total_payments'] += payment['amount']
        
        # Calculate net values and sort
        for key, data in customer_sales.items():
            data['net_revenue'] = data['total_sales_amount'] - data['total_refund_amount']
            data['net_quantity'] = data['total_quantity_sold'] - data['total_quantity_refunded']
            data['outstanding_balance'] = data['net_revenue'] - data['total_payments']
            data['total_transactions'] = data['sales_count'] + data['refund_count']
        
        # Sort customers based on preference
        if sort_by == 'quantity':
            customer_sales = dict(sorted(customer_sales.items(), 
                                       key=lambda x: x[1]['net_quantity'], reverse=True))
        elif sort_by == 'transactions':
            customer_sales = dict(sorted(customer_sales.items(), 
                                       key=lambda x: x[1]['total_transactions'], reverse=True))
        else:  # revenue
            customer_sales = dict(sorted(customer_sales.items(), 
                                       key=lambda x: x[1]['net_revenue'], reverse=True))
        
        # FIXED: Prepare chart data (top 15 customers instead of limiting to 3)
        chart_labels = []
        chart_values = []
        chart_colors = []
        
        # Vibrant color palette for customers
        customer_colors = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57',
            '#FF9FF3', '#54A0FF', '#5F27CD', '#00D2D3', '#FF9F43',
            '#EE5A24', '#009432', '#0652DD', '#9980FA', '#FFC312',
            '#C4E538', '#12CBC4', '#FDA7DF', '#ED4C67', '#F79F1F'
        ]
        
        count = 0
        for key, data in customer_sales.items():
            if count >= 15:  # Show top 15 customers in chart
                break
            
            chart_labels.append(str(data['customer_name']))
            
            if sort_by == 'quantity':
                chart_values.append(float(data['net_quantity']))
            elif sort_by == 'transactions':
                chart_values.append(float(data['total_transactions']))
            else:
                chart_values.append(float(data['net_revenue']))
            
            # Assign color from palette
            chart_colors.append(customer_colors[count % len(customer_colors)])
            count += 1
        
        # PASS JSON STRINGS DIRECTLY
        chart_data = {
            'labels_json': json.dumps(chart_labels),
            'values_json': json.dumps(chart_values),
            'colors_json': json.dumps(chart_colors),
            'metric': sort_by
        }
        
        return render_template('reports/sales_by_customer.html', 
                             customer_sales=customer_sales,
                             sort_by=sort_by,
                             chart_data=chart_data)
    except Exception as e:
        flash(f'Error generating sales by customer report: {str(e)}', 'error')
        return render_template('reports/sales_by_customer.html', 
                             customer_sales={}, 
                             sort_by='revenue', 
                             chart_data={
                                 'labels_json': json.dumps([]),
                                 'values_json': json.dumps([]),
                                 'colors_json': json.dumps([]),
                                 'metric': 'revenue'
                             })
                
@reports_bp.route('/profit')
@login_required
def profit_report():
    try:
        supabase = get_db()
        
        # Get all sales and payments for comprehensive analysis
        sales = supabase.table('sale').select('*').execute().data
        payments = supabase.table('payment').select('*').execute().data
        stock_items = supabase.table('stock').select('*').execute().data
        
        total_profit = 0
        total_revenue = 0
        total_cost = 0
        total_payments_received = sum(payment['amount'] for payment in payments)
        
        profit_by_stock = {}
        monthly_profit = {}
        
        for sale in sales:
            stock_key = f"{sale['stock_size']}_{sale['stock_color']}"
            profit = sale.get('profit', 0)
            revenue = sale['total']
            cost = sale.get('total_cost', 0)
            
            # Extract month for trend analysis
            sale_month = sale['date'][:7] if sale['date'] else '2024-12'  # YYYY-MM format
            
            if sale['is_refund']:
                profit = -profit
                revenue = -revenue
                cost = -cost
            
            total_profit += profit
            total_revenue += revenue
            total_cost += cost
            
            # Monthly profit tracking
            if sale_month not in monthly_profit:
                monthly_profit[sale_month] = {'profit': 0, 'revenue': 0, 'cost': 0}
            monthly_profit[sale_month]['profit'] += profit
            monthly_profit[sale_month]['revenue'] += revenue
            monthly_profit[sale_month]['cost'] += cost
            
            # Stock-wise profit tracking
            if stock_key not in profit_by_stock:
                profit_by_stock[stock_key] = {
                    'stock_item': {'size': sale['stock_size'], 'color': sale['stock_color']},
                    'total_profit': 0,
                    'total_revenue': 0,
                    'total_cost': 0,
                    'sales_count': 0,
                    'profit_margin': 0
                }
            
            profit_by_stock[stock_key]['total_profit'] += profit
            profit_by_stock[stock_key]['total_revenue'] += revenue
            profit_by_stock[stock_key]['total_cost'] += cost
            profit_by_stock[stock_key]['sales_count'] += 1
        
        # Calculate profit margins
        for key, data in profit_by_stock.items():
            if data['total_revenue'] > 0:
                data['profit_margin'] = (data['total_profit'] / data['total_revenue']) * 100
        
        # Sort by profit (descending)
        profit_by_stock = dict(sorted(profit_by_stock.items(), 
                                    key=lambda x: x[1]['total_profit'], reverse=True))
        
        # Calculate overall metrics
        overall_profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
        cash_flow = total_payments_received - total_cost
        
        # Prepare chart data
        stock_labels = []
        stock_profits = []
        stock_colors = []
        
        # Monthly trend data
        months = sorted(monthly_profit.keys())
        monthly_labels = months
        monthly_profits = [monthly_profit[month]['profit'] for month in months]
        monthly_revenues = [monthly_profit[month]['revenue'] for month in months]
        
        # Top profitable stocks (limit to 8 for readability)
        count = 0
        for key, data in profit_by_stock.items():
            if count >= 8:
                break
            
            stock_labels.append(f"{data['stock_item']['size']} {data['stock_item']['color']}")
            stock_profits.append(float(data['total_profit']))
            
            # Color coding based on profitability
            if data['total_profit'] > 0:
                stock_colors.append('#28a745')  # Green for profit
            else:
                stock_colors.append('#dc3545')  # Red for loss
            
            count += 1
        
        chart_data = {
            'stock_labels': json.dumps(stock_labels),
            'stock_profits': json.dumps(stock_profits),
            'stock_colors': json.dumps(stock_colors),
            'monthly_labels': json.dumps(monthly_labels),
            'monthly_profits': json.dumps(monthly_profits),
            'monthly_revenues': json.dumps(monthly_revenues)
        }
        
        # Prepare business insights data in Python
        profitable_items = [item for item in profit_by_stock.values() if item['total_profit'] > 0]
        loss_making_items = [item for item in profit_by_stock.values() if item['total_profit'] < 0]
        break_even_items = [item for item in profit_by_stock.values() if item['total_profit'] == 0]
        
        # Get top 3 profitable items
        top_3_profitable = sorted(profitable_items, key=lambda x: x['total_profit'], reverse=True)[:3]
        
        # Get worst 3 loss-making items
        worst_3_loss = sorted(loss_making_items, key=lambda x: x['total_profit'])[:3]
        
        summary_stats = {
            'total_profit': total_profit,
            'total_revenue': total_revenue,
            'total_cost': total_cost,
            'total_payments_received': total_payments_received,
            'overall_profit_margin': overall_profit_margin,
            'cash_flow': cash_flow,
            'profitable_items': len(profitable_items),
            'loss_making_items': len(loss_making_items),
            'break_even_items': len(break_even_items),
            'top_3_profitable': top_3_profitable,
            'worst_3_loss': worst_3_loss
        }
        
        return render_template('reports/profit.html', 
                             profit_by_stock=profit_by_stock,
                             chart_data=chart_data,
                             summary_stats=summary_stats)
    except Exception as e:
        flash(f'Error generating profit report: {str(e)}', 'error')
        return render_template('reports/profit.html', profit_by_stock={}, chart_data={}, summary_stats={})

# PDF Export Routes using Playwright - USES YOUR EXACT EXISTING TEMPLATES
@reports_bp.route('/export/account_pdf')
@login_required
def export_account_pdf():
    try:
        customer_name = request.args.get('customer')
        customer_phone = request.args.get('phone')
        
        if not customer_name or not customer_phone:
            flash('Customer information required for PDF export.', 'error')
            return redirect(url_for('reports.account_report'))
        
        # Get the EXACT same data as the HTML version
        supabase = get_db()
        customers = supabase.table('customer').select('*').order('name').execute().data
        sales = supabase.table('sale').select('*').eq('customer_name', customer_name).eq('customer_phone', customer_phone).order('date', desc=True).execute().data
        payments = supabase.table('payment').select('*').eq('customer_name', customer_name).eq('customer_phone', customer_phone).order('date', desc=True).execute().data
        transactions = supabase.table('transaction').select('*').eq('customer_name', customer_name).eq('customer_phone', customer_phone).order('date', desc=True).execute().data
        
        # Calculate balance
        total_sales = sum(sale['total'] for sale in sales if not sale['is_refund'])
        total_refunds = sum(sale['total'] for sale in sales if sale['is_refund'])
        total_payments = sum(payment['amount'] for payment in payments)
        total_advances = sum(t['amount'] for t in transactions if t['type'] == 'advance')
        balance = total_sales - total_refunds - total_payments + total_advances
        
        account_data = {
            'customer_name': customer_name,
            'customer_phone': customer_phone,
            'sales': sales,
            'payments': payments,
            'transactions': transactions,
            'total_sales': total_sales,
            'total_refunds': total_refunds,
            'total_payments': total_payments,
            'total_advances': total_advances,
            'balance': balance
        }
        
        # Use your EXISTING PDF template - EXACTLY as you created it
        html_content = render_template('reports/account_pdf.html', 
                                     customers=customers, 
                                     account_data=account_data)
        
        # Convert to PDF using Playwright
        pdf_bytes = html_to_pdf(html_content, f'account_report_{customer_name}')
        
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=account_report_{customer_name.replace(" ", "_")}_{datetime.now().strftime("%Y%m%d")}.pdf'
        
        return response
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('reports.account_report'))

@reports_bp.route('/export/sales_by_customer_pdf')
@login_required
def export_sales_by_customer_pdf():
    try:
        sort_by = request.args.get('sort_by', 'revenue')
        
        # Get EXACT same data as HTML version
        supabase = get_db()
        sales = supabase.table('sale').select('*').execute().data
        payments = supabase.table('payment').select('*').execute().data
        
        customer_sales = {}
        for sale in sales:
            customer_key = f"{sale['customer_name']}|{sale['customer_phone']}"
            if customer_key not in customer_sales:
                customer_sales[customer_key] = {
                    'customer_name': sale['customer_name'],
                    'customer_phone': sale['customer_phone'],
                    'total_quantity_sold': 0,
                    'total_quantity_refunded': 0,
                    'total_sales_amount': 0,
                    'total_refund_amount': 0,
                    'total_payments': 0,
                    'sales_count': 0,
                    'refund_count': 0
                }
            
            if sale['is_refund']:
                customer_sales[customer_key]['total_quantity_refunded'] += sale['quantity']
                customer_sales[customer_key]['total_refund_amount'] += sale['total']
                customer_sales[customer_key]['refund_count'] += 1
            else:
                customer_sales[customer_key]['total_quantity_sold'] += sale['quantity']
                customer_sales[customer_key]['total_sales_amount'] += sale['total']
                customer_sales[customer_key]['sales_count'] += 1
        
        for payment in payments:
            customer_key = f"{payment['customer_name']}|{payment['customer_phone']}"
            if customer_key in customer_sales:
                customer_sales[customer_key]['total_payments'] += payment['amount']
        
        for key, data in customer_sales.items():
            data['net_revenue'] = data['total_sales_amount'] - data['total_refund_amount']
            data['net_quantity'] = data['total_quantity_sold'] - data['total_quantity_refunded']
            data['outstanding_balance'] = data['net_revenue'] - data['total_payments']
            data['total_transactions'] = data['sales_count'] + data['refund_count']
        
        if sort_by == 'quantity':
            customer_sales = dict(sorted(customer_sales.items(), 
                                       key=lambda x: x[1]['net_quantity'], reverse=True))
        elif sort_by == 'transactions':
            customer_sales = dict(sorted(customer_sales.items(), 
                                       key=lambda x: x[1]['total_transactions'], reverse=True))
        else:
            customer_sales = dict(sorted(customer_sales.items(), 
                                       key=lambda x: x[1]['net_revenue'], reverse=True))
        
        chart_labels = []
        chart_values = []
        count = 0
        
        for key, data in customer_sales.items():
            if count >= 10:
                break
            
            chart_labels.append(data['customer_name'])
            
            if sort_by == 'quantity':
                chart_values.append(float(data['net_quantity']))
            elif sort_by == 'transactions':
                chart_values.append(float(data['total_transactions']))
            else:
                chart_values.append(float(data['net_revenue']))
            
            count += 1
        
        chart_data = {
            'labels': json.dumps(chart_labels),
            'values': json.dumps(chart_values),
            'metric': sort_by
        }
        
        # Use your EXISTING PDF template
        html_content = render_template('reports/sales_by_customer_pdf.html', 
                                     customer_sales=customer_sales,
                                     sort_by=sort_by,
                                     chart_data=chart_data)
        
        pdf_bytes = html_to_pdf(html_content, f'sales_by_customer_{sort_by}')
        
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=sales_by_customer_{sort_by}_report_{datetime.now().strftime("%Y%m%d")}.pdf'
        
        return response
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('reports.sales_by_customer'))

@reports_bp.route('/export/sales_by_stock_pdf')
@login_required
def export_sales_by_stock_pdf():
    try:
        group_by = request.args.get('group_by', 'item')
        
        # Copy EXACT logic from sales_by_stock route
        supabase = get_db()
        sales = supabase.table('sale').select('*').execute().data
        stock_items = supabase.table('stock').select('*').execute().data
        
        stock_lookup = {f"{item['size']}_{item['color']}": item for item in stock_items}
        stock_sales = {}
        
        for sale in sales:
            if group_by == 'size':
                group_key = sale['stock_size']
                group_name = sale['stock_size']
            elif group_by == 'color':
                group_key = sale['stock_color']
                group_name = sale['stock_color']
            else:
                group_key = f"{sale['stock_size']}_{sale['stock_color']}"
                group_name = f"{sale['stock_size']} - {sale['stock_color']}"
            
            if group_key not in stock_sales:
                stock_sales[group_key] = {
                    'group_name': group_name,
                    'stock_item': stock_lookup.get(f"{sale['stock_size']}_{sale['stock_color']}", 
                                                 {'size': sale['stock_size'], 'color': sale['stock_color']}),
                    'total_quantity_sold': 0,
                    'total_quantity_refunded': 0,
                    'total_sales_amount': 0,
                    'total_refund_amount': 0,
                    'sales_count': 0,
                    'refund_count': 0
                }
            
            if sale['is_refund']:
                stock_sales[group_key]['total_quantity_refunded'] += sale['quantity']
                stock_sales[group_key]['total_refund_amount'] += sale['total']
                stock_sales[group_key]['refund_count'] += 1
            else:
                stock_sales[group_key]['total_quantity_sold'] += sale['quantity']
                stock_sales[group_key]['total_sales_amount'] += sale['total']
                stock_sales[group_key]['sales_count'] += 1
        
        stock_sales = dict(sorted(stock_sales.items(), 
                                key=lambda x: x[1]['total_sales_amount'] - x[1]['total_refund_amount'], 
                                reverse=True))
        
        chart_data = {}
        if stock_sales:
            chart_labels = []
            chart_values = []
            chart_colors = []
            
            color_map = {
                'Red': '#dc3545', 'Blue': '#0d6efd', 'Black': '#212529', 
                'White': '#6c757d', 'Green': '#198754', 'Yellow': '#ffc107',
                'Purple': '#6f42c1', 'Orange': '#fd7e14', 'Pink': '#d63384',
                'Brown': '#8B4513', 'Grey': '#6c757d', 'Gray': '#6c757d'
            }
            
            for key, data in stock_sales.items():
                net_revenue = data['total_sales_amount'] - data['total_refund_amount']
                chart_labels.append(data['group_name'])
                chart_values.append(float(net_revenue))
                
                if group_by == 'color':
                    chart_colors.append(color_map.get(data['group_name'], '#6c757d'))
                else:
                    chart_colors.append('#0d6efd')
            
            chart_data = {
                'labels': json.dumps(chart_labels),
                'values': json.dumps(chart_values),
                'colors': json.dumps(chart_colors)
            }
        
        # Use your EXISTING PDF template
        html_content = render_template('reports/sales_by_stock_pdf.html', 
                                     stock_sales=stock_sales, 
                                     group_by=group_by,
                                     chart_data=chart_data)
        
        pdf_bytes = html_to_pdf(html_content, f'sales_by_{group_by}')
        
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=sales_by_{group_by}_report_{datetime.now().strftime("%Y%m%d")}.pdf'
        
        return response
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('reports.sales_by_stock'))

@reports_bp.route('/export/profit_pdf')
@login_required
def export_profit_pdf():
    try:
        # Copy EXACT logic from profit_report route
        supabase = get_db()
        sales = supabase.table('sale').select('*').execute().data
        payments = supabase.table('payment').select('*').execute().data
        
        total_profit = 0
        total_revenue = 0
        total_cost = 0
        total_payments_received = sum(payment['amount'] for payment in payments)
        
        profit_by_stock = {}
        monthly_profit = {}
        
        for sale in sales:
            stock_key = f"{sale['stock_size']}_{sale['stock_color']}"
            profit = sale.get('profit', 0)
            revenue = sale['total']
            cost = sale.get('total_cost', 0)
            
            sale_month = sale['date'][:7] if sale['date'] else '2024-12'
            
            if sale['is_refund']:
                profit = -profit
                revenue = -revenue
                cost = -cost
            
            total_profit += profit
            total_revenue += revenue
            total_cost += cost
            
            if sale_month not in monthly_profit:
                monthly_profit[sale_month] = {'profit': 0, 'revenue': 0, 'cost': 0}
            monthly_profit[sale_month]['profit'] += profit
            monthly_profit[sale_month]['revenue'] += revenue
            monthly_profit[sale_month]['cost'] += cost
            
            if stock_key not in profit_by_stock:
                profit_by_stock[stock_key] = {
                    'stock_item': {'size': sale['stock_size'], 'color': sale['stock_color']},
                    'total_profit': 0,
                    'total_revenue': 0,
                    'total_cost': 0,
                    'sales_count': 0,
                    'profit_margin': 0
                }
            
            profit_by_stock[stock_key]['total_profit'] += profit
            profit_by_stock[stock_key]['total_revenue'] += revenue
            profit_by_stock[stock_key]['total_cost'] += cost
            profit_by_stock[stock_key]['sales_count'] += 1
        
        for key, data in profit_by_stock.items():
            if data['total_revenue'] > 0:
                data['profit_margin'] = (data['total_profit'] / data['total_revenue']) * 100
        
        profit_by_stock = dict(sorted(profit_by_stock.items(), 
                                    key=lambda x: x[1]['total_profit'], reverse=True))
        
        overall_profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
        cash_flow = total_payments_received - total_cost
        
        stock_labels = []
        stock_profits = []
        stock_colors = []
        
        months = sorted(monthly_profit.keys())
        monthly_labels = months
        monthly_profits = [monthly_profit[month]['profit'] for month in months]
        monthly_revenues = [monthly_profit[month]['revenue'] for month in months]
        
        count = 0
        for key, data in profit_by_stock.items():
            if count >= 8:
                break
            
            stock_labels.append(f"{data['stock_item']['size']} {data['stock_item']['color']}")
            stock_profits.append(float(data['total_profit']))
            
            if data['total_profit'] > 0:
                stock_colors.append('#28a745')
            else:
                stock_colors.append('#dc3545')
            
            count += 1
        
        chart_data = {
            'stock_labels': json.dumps(stock_labels),
            'stock_profits': json.dumps(stock_profits),
            'stock_colors': json.dumps(stock_colors),
            'monthly_labels': json.dumps(monthly_labels),
            'monthly_profits': json.dumps(monthly_profits),
            'monthly_revenues': json.dumps(monthly_revenues)
        }
        
        profitable_items = [item for item in profit_by_stock.values() if item['total_profit'] > 0]
        loss_making_items = [item for item in profit_by_stock.values() if item['total_profit'] < 0]
        break_even_items = [item for item in profit_by_stock.values() if item['total_profit'] == 0]
        
        top_3_profitable = sorted(profitable_items, key=lambda x: x['total_profit'], reverse=True)[:3]
        worst_3_loss = sorted(loss_making_items, key=lambda x: x['total_profit'])[:3]
        
        summary_stats = {
            'total_profit': total_profit,
            'total_revenue': total_revenue,
            'total_cost': total_cost,
            'total_payments_received': total_payments_received,
            'overall_profit_margin': overall_profit_margin,
            'cash_flow': cash_flow,
            'profitable_items': len(profitable_items),
            'loss_making_items': len(loss_making_items),
            'break_even_items': len(break_even_items),
            'top_3_profitable': top_3_profitable,
            'worst_3_loss': worst_3_loss
        }
        
        # Use your EXISTING PDF template
        html_content = render_template('reports/profit_pdf.html', 
                                     profit_by_stock=profit_by_stock,
                                     chart_data=chart_data,
                                     summary_stats=summary_stats)
        
        pdf_bytes = html_to_pdf(html_content, 'profit_analysis')
        
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=profit_analysis_report_{datetime.now().strftime("%Y%m%d")}.pdf'
        
        return response
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('reports.profit_report'))