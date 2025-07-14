from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
from app.database import get_db
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO
from datetime import datetime

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/')
def index():
    return render_template('reports/index.html')

@reports_bp.route('/account')
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
def sales_by_stock():
    try:
        supabase = get_db()
        
        # Get all sales with stock information
        sales = supabase.table('sale').select('*').execute().data
        stock_items = supabase.table('stock').select('*').execute().data
        
        # Create stock lookup using size and color as key
        stock_lookup = {f"{item['size']}_{item['color']}": item for item in stock_items}
        
        # Group sales by stock
        stock_sales = {}
        for sale in sales:
            stock_key = f"{sale['stock_size']}_{sale['stock_color']}"
            if stock_key not in stock_sales:
                stock_sales[stock_key] = {
                    'stock_item': stock_lookup.get(stock_key, {'size': sale['stock_size'], 'color': sale['stock_color']}),
                    'total_quantity_sold': 0,
                    'total_quantity_refunded': 0,
                    'total_sales_amount': 0,
                    'total_refund_amount': 0,
                    'sales_count': 0,
                    'refund_count': 0
                }
            
            if sale['is_refund']:
                stock_sales[stock_key]['total_quantity_refunded'] += sale['quantity']
                stock_sales[stock_key]['total_refund_amount'] += sale['total']
                stock_sales[stock_key]['refund_count'] += 1
            else:
                stock_sales[stock_key]['total_quantity_sold'] += sale['quantity']
                stock_sales[stock_key]['total_sales_amount'] += sale['total']
                stock_sales[stock_key]['sales_count'] += 1
        
        return render_template('reports/sales_by_stock.html', stock_sales=stock_sales)
    except Exception as e:
        flash(f'Error generating sales by stock report: {str(e)}', 'error')
        return render_template('reports/sales_by_stock.html', stock_sales={})

@reports_bp.route('/sales_by_customer')
def sales_by_customer():
    try:
        supabase = get_db()
        
        # Get all sales
        sales = supabase.table('sale').select('*').execute().data
        
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
        
        return render_template('reports/sales_by_customer.html', customer_sales=customer_sales)
    except Exception as e:
        flash(f'Error generating sales by customer report: {str(e)}', 'error')
        return render_template('reports/sales_by_customer.html', customer_sales={})

@reports_bp.route('/profit')
def profit_report():
    try:
        supabase = get_db()
        
        # Get all sales
        sales = supabase.table('sale').select('*').execute().data
        
        total_profit = 0
        profit_by_stock = {}
        
        for sale in sales:
            stock_key = f"{sale['stock_size']}_{sale['stock_color']}"
            profit = sale.get('profit', 0)  # Use the profit field from the sale record
            
            if sale['is_refund']:
                profit = -profit  # Negative profit for refunds
            
            total_profit += profit
            
            if stock_key not in profit_by_stock:
                profit_by_stock[stock_key] = {
                    'stock_item': {'size': sale['stock_size'], 'color': sale['stock_color']},
                    'total_profit': 0,
                    'sales_count': 0
                }
            
            profit_by_stock[stock_key]['total_profit'] += profit
            profit_by_stock[stock_key]['sales_count'] += 1
        
        return render_template('reports/profit.html', 
                             total_profit=total_profit, 
                             profit_by_stock=profit_by_stock)
    except Exception as e:
        flash(f'Error generating profit report: {str(e)}', 'error')
        return render_template('reports/profit.html', total_profit=0, profit_by_stock={})

@reports_bp.route('/export/account_pdf')
def export_account_pdf():
    try:
        customer_name = request.args.get('customer')
        customer_phone = request.args.get('phone')
        
        if not customer_name or not customer_phone:
            flash('Customer information required for PDF export.', 'error')
            return redirect(url_for('reports.account_report'))
        
        supabase = get_db()
        
        # Get customer data
        sales = supabase.table('sale').select('*').eq('customer_name', customer_name).eq('customer_phone', customer_phone).order('date', desc=True).execute().data
        payments = supabase.table('payment').select('*').eq('customer_name', customer_name).eq('customer_phone', customer_phone).order('date', desc=True).execute().data
        transactions = supabase.table('transaction').select('*').eq('customer_name', customer_name).eq('customer_phone', customer_phone).order('date', desc=True).execute().data
        
        # Calculate totals
        total_sales = sum(sale['total'] for sale in sales if not sale['is_refund'])
        total_refunds = sum(sale['total'] for sale in sales if sale['is_refund'])
        total_payments = sum(payment['amount'] for payment in payments)
        balance = total_sales - total_refunds - total_payments
        
        # Create PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=1  # Center alignment
        )
        story.append(Paragraph(f"Account Report - {customer_name}", title_style))
        story.append(Spacer(1, 12))
        
        # Customer info
        story.append(Paragraph(f"<b>Phone:</b> {customer_phone}", styles['Normal']))
        story.append(Paragraph(f"<b>Report Date:</b> {datetime.now().strftime('%Y-%m-%d')}", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Summary table
        summary_data = [
            ['Summary', 'Amount'],
            ['Total Sales', f'₦{total_sales:.2f}'],
            ['Total Refunds', f'₦{total_refunds:.2f}'],
            ['Total Payments', f'₦{total_payments:.2f}'],
            ['Outstanding Balance', f'₦{balance:.2f}']
        ]
        
        summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 30))
        
        # Sales table
        if sales:
            story.append(Paragraph("Sales History", styles['Heading2']))
            sales_data = [['Date', 'Type', 'Size/Color', 'Quantity', 'Rate', 'Total']]
            for sale in sales:
                sales_data.append([
                    sale['date'][:10] if sale['date'] else 'N/A',
                    'Refund' if sale['is_refund'] else 'Sale',
                    f"{sale['stock_size']}/{sale['stock_color']}",
                    str(sale['quantity']),
                    f"₦{sale['rate']:.2f}",
                    f"₦{sale['total']:.2f}"
                ])
            
            sales_table = Table(sales_data)
            sales_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(sales_table)
        
        doc.build(story)
        buffer.seek(0)
        
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=account_report_{customer_name}_{datetime.now().strftime("%Y%m%d")}.pdf'
        
        return response
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('reports.account_report'))