import os
import secrets
from datetime import datetime
from flask import render_template, url_for, flash, redirect, request, jsonify, abort
from flask_login import login_user, current_user, logout_user, login_required
from werkzeug.utils import secure_filename
from app import app, db
from forms import (
    RegistrationForm, LoginForm, ProductForm, InventoryForm, 
    OrderForm, OrderItemForm
)
from models import (
    User, Product, Inventory, Order, OrderItem, Notification,
    Role, OrderStatus, ProductCategory, ProductGender
)
from utils import generate_order_number, can_view_product, can_edit_product, can_delete_product, get_role_display_name
# Import the filters to make them available in templates
import filters

# Home page
@app.route('/')
def index():
    return render_template('index.html')

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Login failed. Please check email and password.', 'danger')
    
    return render_template('login.html', form=form)

# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            role=form.role.data,
            company_name=form.company_name.data if form.company_name.data else None
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        
        flash(f'Account created successfully! You can now log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html', form=form)

# Logout route
@app.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# Dashboard route
@app.route('/dashboard')
@login_required
def dashboard():
    inventory_count = Inventory.query.filter_by(user_id=current_user.id).count()
    
    # Count of open orders (both as customer and supplier)
    open_orders_count = (
        Order.query.filter(
            (Order.customer_id == current_user.id) | 
            (Order.supplier_id == current_user.id)
        ).filter(
            Order.status.in_([OrderStatus.PENDING, OrderStatus.PROCESSING])
        ).count()
    )
    
    # Count of low stock items
    inventory_items = Inventory.query.filter_by(user_id=current_user.id).all()
    low_stock_count = sum(1 for item in inventory_items if item.quantity <= item.min_stock_level)
    
    # Get low stock items for the alert section
    low_stock_items = Inventory.query.filter_by(user_id=current_user.id).filter(
        Inventory.quantity <= Inventory.min_stock_level
    ).join(Product).limit(3).all()
    
    # Recent activities (notifications)
    recent_activities = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()
    ).limit(5).all()
    
    # Products for quick inventory adjustment
    products = Product.query.all()
    
    # Count of unread notifications
    unread_count = Notification.query.filter_by(user_id=current_user.id, read=False).count()
    
    return render_template(
        'dashboard.html',
        inventory_count=inventory_count,
        open_orders_count=open_orders_count,
        low_stock_count=low_stock_count,
        low_stock_items=low_stock_items,
        recent_activities=recent_activities,
        products=products,
        unread_count=unread_count,
        Role=Role,
        ProductCategory=ProductCategory,
        ProductGender=ProductGender
    )

# Products route
@app.route('/products')
@login_required
def products():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    products_query = Product.query.order_by(Product.created_at.desc())
    
    # Filter by category if provided
    category = request.args.get('category')
    if category:
        products_query = products_query.filter_by(category=category)
    
    # Filter by gender if provided
    gender = request.args.get('gender')
    if gender:
        products_query = products_query.filter_by(gender=gender)
    
    # Search by name or SKU if provided
    search = request.args.get('search')
    if search:
        products_query = products_query.filter(
            (Product.name.ilike(f'%{search}%')) | (Product.sku.ilike(f'%{search}%'))
        )
    
    # Pagination
    products_pagination = products_query.paginate(page=page, per_page=per_page)
    
    # Get inventory data for these products
    inventory_data = {}
    inventory_items = Inventory.query.filter_by(user_id=current_user.id).all()
    for item in inventory_items:
        inventory_data[item.product_id] = {
            'quantity': item.quantity,
            'min_stock_level': item.min_stock_level
        }
    
    return render_template(
        'products/index.html',
        products=products_pagination,
        inventory_data=inventory_data,
        ProductCategory=ProductCategory,
        categories=[
            (ProductCategory.TSHIRT, 'T-Shirt'),
            (ProductCategory.SHOES, 'Shoes'),
            (ProductCategory.ACCESSORIES, 'Accessories'),
            (ProductCategory.DRESS, 'Dress')
        ],
        genders=[
            (ProductGender.MENS, "Men's"),
            (ProductGender.WOMENS, "Women's"),
            (ProductGender.UNISEX, 'Unisex')
        ]
    )

# Create product route
@app.route('/products/create', methods=['GET', 'POST'])
@login_required
def create_product():
    # Only manufacturers can create products
    if current_user.role != Role.MANUFACTURER:
        flash('Only manufacturers can create products.', 'warning')
        return redirect(url_for('products'))
    
    form = ProductForm()
    if form.validate_on_submit():
        try:
            # Generate a random SKU if not provided
            sku = form.sku.data
            if not sku:
                sku = f"P{secrets.token_hex(4).upper()}"
            
            # Handle image upload if provided
            image_path = None
            if form.image.data:
                image_file = form.image.data
                filename = secure_filename(image_file.filename)
                random_hex = secrets.token_hex(8)
                _, file_ext = os.path.splitext(filename)
                image_filename = f"{random_hex}{file_ext}"
                image_path = os.path.join('static/uploads', image_filename)
                
                # Save the file
                image_file.save(os.path.join(app.root_path, image_path))
            
            # Create new product
            product = Product(
                name=form.name.data,
                description=form.description.data,
                sku=sku,
                category=form.category.data,
                size=form.size.data,
                color=form.color.data,
                pattern=form.pattern.data,
                gender=form.gender.data,
                price=form.price.data,
                image_path=image_path
            )
            
            db.session.add(product)
            db.session.commit()
            
            # Add to the manufacturer's inventory
            inventory = Inventory(
                user_id=current_user.id,
                product_id=product.id,
                quantity=0,
                min_stock_level=10
            )
            
            db.session.add(inventory)
            db.session.commit()
            
            flash(f'Product "{product.name}" created successfully!', 'success')
            return redirect(url_for('products'))
        except Exception as e:
            db.session.rollback()
            # Handle duplicate SKU error specifically
            if "duplicate key value violates unique constraint" in str(e) and "product_sku_key" in str(e):
                flash('This SKU is already in use. Please use a unique SKU.', 'danger')
            else:
                flash(f'An error occurred: {str(e)}', 'danger')
            # Log the error for debugging
            app.logger.error(f"Error creating product: {str(e)}")
    
    return render_template('products/create.html', form=form)

# View product details
@app.route('/products/<int:product_id>')
@login_required
def view_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    # Check if the user can view this product
    if not can_view_product(current_user, product):
        flash('You do not have permission to view this product.', 'warning')
        return redirect(url_for('products'))
    
    # Get inventory data for this product
    inventory_item = Inventory.query.filter_by(
        user_id=current_user.id, 
        product_id=product.id
    ).first()
    
    # Get supplier inventory data for retailers/customers/wholesalers
    supplier_inventory_data = {}
    if current_user.role in ['retailer', 'customer', 'wholesaler']:
        # Query inventory from potential suppliers (manufacturers for wholesalers, 
        # wholesalers for retailers, retailers for customers)
        supplier_role_map = {
            'wholesaler': 'manufacturer',
            'retailer': 'wholesaler',
            'customer': 'retailer'
        }
        
        supplier_role = supplier_role_map.get(current_user.role)
        if supplier_role:
            # Get all potential suppliers with this role
            suppliers = User.query.filter_by(role=supplier_role).all()
            supplier_ids = [supplier.id for supplier in suppliers]
            
            # Get inventory for this product from suppliers
            supplier_inventories = Inventory.query.filter(
                Inventory.user_id.in_(supplier_ids),
                Inventory.product_id == product.id,
                Inventory.quantity > 0
            ).all()
            
            # Use the first available supplier inventory
            if supplier_inventories:
                supplier_inventory_data[product.id] = supplier_inventories[0]
    
    # Create a form for CSRF protection in the delete form
    from flask_wtf import FlaskForm
    delete_form = FlaskForm()
    
    return render_template(
        'products/view.html',
        product=product,
        inventory=inventory_item,
        supplier_inventory_data=supplier_inventory_data,
        can_edit=can_edit_product(current_user, product),
        can_delete=can_delete_product(current_user, product),
        can_edit_product=can_edit_product,
        can_delete_product=can_delete_product,
        form=delete_form
    )

# Edit product
@app.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    # Check if the user can edit this product
    if not can_edit_product(current_user, product):
        flash('You do not have permission to edit this product.', 'warning')
        return redirect(url_for('view_product', product_id=product.id))
    
    form = ProductForm()
    form.product_id = product.id  # Set product_id for the SKU validator
    
    if form.validate_on_submit():
        try:
            # Update product data
            product.name = form.name.data
            product.description = form.description.data
            product.sku = form.sku.data
            product.category = form.category.data
            product.size = form.size.data
            product.color = form.color.data
            product.pattern = form.pattern.data
            product.gender = form.gender.data
            product.price = form.price.data
            
            # Handle image upload if provided
            if form.image.data:
                # Delete old image if exists
                if product.image_path:
                    old_image_path = os.path.join(app.root_path, product.image_path)
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
                
                # Save new image
                image_file = form.image.data
                filename = secure_filename(image_file.filename)
                random_hex = secrets.token_hex(8)
                _, file_ext = os.path.splitext(filename)
                image_filename = f"{random_hex}{file_ext}"
                image_path = os.path.join('static/uploads', image_filename)
                
                image_file.save(os.path.join(app.root_path, image_path))
                product.image_path = image_path
            
            db.session.commit()
            
            flash(f'Product "{product.name}" updated successfully!', 'success')
            return redirect(url_for('view_product', product_id=product.id))
        except Exception as e:
            db.session.rollback()
            # Handle duplicate SKU error specifically
            if "duplicate key value violates unique constraint" in str(e) and "product_sku_key" in str(e):
                flash('This SKU is already in use. Please use a unique SKU.', 'danger')
            else:
                flash(f'An error occurred: {str(e)}', 'danger')
            # Log the error for debugging
            app.logger.error(f"Error updating product: {str(e)}")
    
    # Fill form with existing data
    if request.method == 'GET':
        form.name.data = product.name
        form.description.data = product.description
        form.sku.data = product.sku
        form.category.data = product.category
        form.size.data = product.size
        form.color.data = product.color
        form.pattern.data = product.pattern
        form.gender.data = product.gender
        form.price.data = product.price
    
    return render_template('products/edit.html', form=form, product=product)

# Delete product
@app.route('/products/<int:product_id>/delete', methods=['POST'])
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    # Check if the user can delete this product
    if not can_delete_product(current_user, product):
        flash('You do not have permission to delete this product.', 'warning')
        return redirect(url_for('view_product', product_id=product.id))
    
    try:
        # Get the product name before deletion for success message
        product_name = product.name
        
        # Delete associated inventory items
        Inventory.query.filter_by(product_id=product.id).delete()
        
        # Delete the image file if exists
        if product.image_path:
            image_path = os.path.join(app.root_path, product.image_path)
            if os.path.exists(image_path):
                os.remove(image_path)
        
        # Check if the product is used in any order items
        order_items = OrderItem.query.filter_by(product_id=product.id).first()
        if order_items:
            flash('Cannot delete this product because it is used in one or more orders.', 'danger')
            return redirect(url_for('view_product', product_id=product.id))
        
        # Delete the product
        db.session.delete(product)
        db.session.commit()
        
        flash(f'Product "{product_name}" has been deleted.', 'success')
        return redirect(url_for('products'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting product: {str(e)}', 'danger')
        app.logger.error(f"Error deleting product: {str(e)}")
        return redirect(url_for('view_product', product_id=product.id))

# Inventory management route
@app.route('/inventory')
@login_required
def inventory():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Base query for user's inventory
    inventory_query = Inventory.query.filter_by(user_id=current_user.id).join(Product)
    
    # Filter by low stock if requested
    filter_type = request.args.get('filter')
    if filter_type == 'low_stock':
        inventory_query = inventory_query.filter(Inventory.quantity <= Inventory.min_stock_level)
    
    # Filter by category if provided
    category = request.args.get('category')
    if category:
        inventory_query = inventory_query.filter(Product.category == category)
    
    # Search by product name or SKU
    search = request.args.get('search')
    if search:
        inventory_query = inventory_query.filter(
            (Product.name.ilike(f'%{search}%')) | (Product.sku.ilike(f'%{search}%'))
        )
    
    # Order by product name by default
    inventory_query = inventory_query.order_by(Product.name)
    
    # Paginate results
    inventory_pagination = inventory_query.paginate(page=page, per_page=per_page)
    
    return render_template(
        'inventory/index.html',
        inventory=inventory_pagination,
        ProductCategory=ProductCategory,
        categories=[
            (ProductCategory.TSHIRT, 'T-Shirt'),
            (ProductCategory.SHOES, 'Shoes'),
            (ProductCategory.ACCESSORIES, 'Accessories'),
            (ProductCategory.DRESS, 'Dress')
        ]
    )

# Update inventory
@app.route('/inventory/<int:inventory_id>', methods=['GET', 'POST'])
@login_required
def update_inventory(inventory_id):
    if inventory_id == 0:
        # This is a quick inventory adjustment from the dashboard
        product_id = request.form.get('product_id', type=int)
        if not product_id:
            flash('Please select a product.', 'warning')
            return redirect(url_for('dashboard'))
        
        inventory_item = Inventory.query.filter_by(
            user_id=current_user.id,
            product_id=product_id
        ).first()
        
        if not inventory_item:
            # Create new inventory entry for this product
            inventory_item = Inventory(
                user_id=current_user.id,
                product_id=product_id,
                quantity=0,
                min_stock_level=10
            )
            db.session.add(inventory_item)
            db.session.commit()
        
        # Update inventory with form data
        inventory_item.quantity = request.form.get('quantity', type=int)
        inventory_item.min_stock_level = request.form.get('min_stock_level', type=int)
        
        db.session.commit()
        
        flash('Inventory updated successfully!', 'success')
        return redirect(url_for('dashboard'))
    else:
        # Regular inventory update
        inventory_item = Inventory.query.get_or_404(inventory_id)
        
        # Ensure the user owns this inventory item
        if inventory_item.user_id != current_user.id:
            flash('You do not have permission to update this inventory item.', 'warning')
            return redirect(url_for('inventory'))
        
        form = InventoryForm()
        
        if form.validate_on_submit():
            # Update inventory with form data
            inventory_item.quantity = form.quantity.data
            inventory_item.min_stock_level = form.min_stock_level.data
            
            db.session.commit()
            
            flash('Inventory updated successfully!', 'success')
            return redirect(url_for('inventory'))
        
        # Fill form with existing data for GET request
        if request.method == 'GET':
            form.product_id.data = inventory_item.product_id
            form.quantity.data = inventory_item.quantity
            form.min_stock_level.data = inventory_item.min_stock_level
        
        return render_template(
            'inventory/update.html',
            form=form,
            inventory_item=inventory_item,
            product=inventory_item.product
        )

# Orders management route
@app.route('/orders')
@login_required
def orders():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Base query
    order_type = request.args.get('type', 'placed')
    
    if order_type == 'placed':
        # Orders placed by current user
        orders_query = Order.query.filter_by(customer_id=current_user.id)
        title = "Orders You've Placed"
    else:
        # Orders to be fulfilled by current user
        orders_query = Order.query.filter_by(supplier_id=current_user.id)
        title = "Orders to Fulfill"
    
    # Filter by status if provided
    status = request.args.get('status')
    if status:
        orders_query = orders_query.filter_by(status=status)
    
    # Order by most recent first
    orders_query = orders_query.order_by(Order.created_at.desc())
    
    # Paginate results
    orders_pagination = orders_query.paginate(page=page, per_page=per_page)
    
    return render_template(
        'orders/index.html',
        orders=orders_pagination,
        title=title,
        order_type=order_type,
        OrderStatus=OrderStatus
    )

# Create new order
@app.route('/orders/create', methods=['GET', 'POST'])
@login_required
def create_order():
    form = OrderForm()
    
    # Check if a specific product was requested
    product_id = request.args.get('product_id', type=int)
    product = None
    if product_id:
        product = Product.query.get_or_404(product_id)
    
    # Populate supplier dropdown based on user role
    if current_user.role == Role.CUSTOMER:
        suppliers = User.query.filter_by(role=Role.RETAILER).all()
    elif current_user.role == Role.RETAILER:
        suppliers = User.query.filter_by(role=Role.WHOLESALER).all()
    elif current_user.role == Role.WHOLESALER:
        suppliers = User.query.filter_by(role=Role.MANUFACTURER).all()
    else:  # Manufacturer can't place orders in this system
        flash('Manufacturers cannot place orders in this system.', 'warning')
        return redirect(url_for('orders'))
    
    # If product is specified, filter suppliers to only those who have this product in stock
    if product:
        supplier_ids_with_stock = [
            inventory.user_id for inventory in 
            Inventory.query.filter_by(product_id=product.id).filter(Inventory.quantity > 0).all()
            if inventory.user_id in [s.id for s in suppliers]
        ]
        suppliers = [s for s in suppliers if s.id in supplier_ids_with_stock]
        if not suppliers:
            flash(f'No suppliers have {product.name} in stock.', 'warning')
            return redirect(url_for('products'))
    
    form.supplier_id.choices = [(s.id, f"{s.company_name or s.username}") for s in suppliers]
    
    if form.validate_on_submit():
        # Create new order
        order = Order(
            order_number=generate_order_number(),
            customer_id=current_user.id,
            supplier_id=form.supplier_id.data,
            status=OrderStatus.PENDING,
            customer_notes=form.customer_notes.data
        )
        
        db.session.add(order)
        db.session.commit()
        
        # Create notification for supplier
        notification = Notification(
            user_id=order.supplier_id,
            message=f"New order #{order.order_number} received from {current_user.username}",
            notification_type='order',
            related_id=order.id
        )
        
        db.session.add(notification)
        db.session.commit()
        
        flash(f'Order #{order.order_number} created successfully!', 'success')
        
        # If a product was specified in the URL, add it to the order automatically
        if product and product_id:
            supplier_inventory = Inventory.query.filter_by(
                user_id=order.supplier_id,
                product_id=product_id
            ).first()
            
            if supplier_inventory and supplier_inventory.quantity > 0:
                # Add the product to the order
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=product_id,
                    quantity=1,  # Default to 1, user can change later
                    unit_price=product.price
                )
                
                db.session.add(order_item)
                
                # Update order total
                order.total_amount = product.price  # Just this item for now
                db.session.commit()
                
                flash(f'Added {product.name} to your order.', 'success')
        
        return redirect(url_for('view_order', order_id=order.id))
    
    return render_template('orders/create.html', form=form, product=product)

# View order details
@app.route('/orders/<int:order_id>')
@login_required
def view_order(order_id):
    order = Order.query.get_or_404(order_id)
    
    # Ensure the user is either the customer or supplier
    if order.customer_id != current_user.id and order.supplier_id != current_user.id:
        flash('You do not have permission to view this order.', 'warning')
        return redirect(url_for('orders'))
    
    # Check if there are no items yet
    has_items = len(order.items) > 0
    
    # Calculate order total
    order_total = sum(item.quantity * item.unit_price for item in order.items)
    
    # Create the order item form for adding items
    item_form = None
    if order.status == OrderStatus.PENDING and order.customer_id == current_user.id:
        item_form = OrderItemForm()
        # Populate product choices based on supplier's inventory
        supplier_inventory = Inventory.query.filter_by(user_id=order.supplier_id).join(Product).all()
        product_choices = [
            (item.product_id, f"{item.product.name} (${item.product.price:.2f})")
            for item in supplier_inventory if item.quantity > 0
        ]
        item_form.product_id.choices = product_choices
    
    return render_template(
        'orders/view.html',
        order=order,
        has_items=has_items,
        order_total=order_total,
        OrderStatus=OrderStatus,
        item_form=item_form,
        is_customer=order.customer_id == current_user.id,
        is_supplier=order.supplier_id == current_user.id
    )

# Add item to order
@app.route('/orders/<int:order_id>/items/add', methods=['GET', 'POST'])
@login_required
def add_order_item(order_id):
    order = Order.query.get_or_404(order_id)
    
    # Ensure the user is the customer
    if order.customer_id != current_user.id:
        flash('You do not have permission to add items to this order.', 'warning')
        return redirect(url_for('view_order', order_id=order.id))
    
    # Cannot add items to orders that are not pending
    if order.status != OrderStatus.PENDING:
        flash('Cannot add items to orders that are not in the pending state.', 'warning')
        return redirect(url_for('view_order', order_id=order.id))
    
    form = OrderItemForm()
    
    # Populate product choices based on supplier's inventory
    supplier_inventory = Inventory.query.filter_by(user_id=order.supplier_id).join(Product).all()
    product_choices = [
        (item.product_id, f"{item.product.name} (${item.product.price:.2f})")
        for item in supplier_inventory if item.quantity > 0
    ]
    
    form.product_id.choices = product_choices
    
    if form.validate_on_submit():
        # Get the product
        product = Product.query.get_or_404(form.product_id.data)
        
        # Get supplier inventory level
        supplier_inventory = Inventory.query.filter_by(
            user_id=order.supplier_id,
            product_id=product.id
        ).first()
        
        # Check if there's enough inventory
        if not supplier_inventory or supplier_inventory.quantity < form.quantity.data:
            max_quantity = supplier_inventory.quantity if supplier_inventory else 0
            flash(f'Not enough inventory available. Maximum quantity available: {max_quantity}', 'danger')
            return redirect(url_for('add_order_item', order_id=order.id))
        
        # Add order item with product price
        order_item = OrderItem(
            order_id=order.id,
            product_id=form.product_id.data,
            quantity=form.quantity.data,
            unit_price=product.price  # Use product price directly
        )
        
        # Add item to session so we can commit it and get all items including the new one
        db.session.add(order_item)
        db.session.flush()
        
        # Update order total by recalculating from all items
        order.total_amount = sum(item.quantity * item.unit_price for item in order.items)
        
        db.session.commit()
        
        flash('Item added to order successfully!', 'success')
        return redirect(url_for('view_order', order_id=order.id))
    
    # Pre-select product if product_id is in URL query string
    product_id = request.args.get('product_id', type=int)
    if product_id:
        product = Product.query.get(product_id)
        if product:
            form.product_id.data = product_id
    
    return render_template(
        'orders/add_item.html',
        form=form,
        order=order
    )

# Update order status
@app.route('/orders/<int:order_id>/status', methods=['POST'])
@login_required
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    
    # Ensure the user is either the customer or supplier
    if order.customer_id != current_user.id and order.supplier_id != current_user.id:
        flash('You do not have permission to update this order.', 'warning')
        return redirect(url_for('orders'))
    
    new_status = request.form.get('status')
    if not new_status or new_status not in [
        OrderStatus.PROCESSING, OrderStatus.SHIPPED, 
        OrderStatus.DELIVERED, OrderStatus.CANCELLED
    ]:
        flash('Invalid order status.', 'danger')
        return redirect(url_for('view_order', order_id=order.id))
    
    # Status change validation based on user role and current status
    if current_user.id == order.supplier_id:
        # Supplier can process, ship, or cancel
        if order.status == OrderStatus.PENDING and new_status in [OrderStatus.PROCESSING, OrderStatus.CANCELLED]:
            pass  # Valid transition
        elif order.status == OrderStatus.PROCESSING and new_status in [OrderStatus.SHIPPED, OrderStatus.CANCELLED]:
            pass  # Valid transition
        else:
            flash('Invalid status transition for supplier.', 'danger')
            return redirect(url_for('view_order', order_id=order.id))
    elif current_user.id == order.customer_id:
        # Customer can cancel if pending or mark as delivered (received) if shipped
        if order.status == OrderStatus.PENDING and new_status == OrderStatus.CANCELLED:
            pass  # Valid transition
        elif order.status == OrderStatus.SHIPPED and new_status == OrderStatus.DELIVERED:
            pass  # Valid transition - customer received the order
        else:
            flash('Invalid status transition for customer.', 'danger')
            return redirect(url_for('view_order', order_id=order.id))
    
    # Handle inventory updates for status changes
    if new_status == OrderStatus.PROCESSING and order.status == OrderStatus.PENDING:
        # Deduct items from supplier inventory
        for item in order.items:
            supplier_inventory = Inventory.query.filter_by(
                user_id=order.supplier_id,
                product_id=item.product_id
            ).first()
            
            if supplier_inventory:
                if supplier_inventory.quantity >= item.quantity:
                    supplier_inventory.quantity -= item.quantity
                else:
                    flash(f'Not enough inventory for {item.product.name}. Order status not updated.', 'danger')
                    return redirect(url_for('view_order', order_id=order.id))
    
    elif new_status == OrderStatus.DELIVERED and order.status == OrderStatus.SHIPPED:
        # Add items to customer inventory
        for item in order.items:
            customer_inventory = Inventory.query.filter_by(
                user_id=order.customer_id,
                product_id=item.product_id
            ).first()
            
            if customer_inventory:
                customer_inventory.quantity += item.quantity
            else:
                # Create new inventory entry for customer
                new_inventory = Inventory(
                    user_id=order.customer_id,
                    product_id=item.product_id,
                    quantity=item.quantity,
                    min_stock_level=10
                )
                db.session.add(new_inventory)
    
    # Update order status
    old_status = order.status
    order.status = new_status
    order.updated_at = datetime.utcnow()
    
    # Create notification for the other party
    recipient_id = order.supplier_id if current_user.id == order.customer_id else order.customer_id
    
    # Different messages based on who made the status change
    if current_user.id == order.customer_id and new_status == OrderStatus.DELIVERED:
        status_message = {
            OrderStatus.PROCESSING: 'is now being processed',
            OrderStatus.SHIPPED: 'has been shipped',
            OrderStatus.DELIVERED: 'has been received by the customer',
            OrderStatus.CANCELLED: 'has been cancelled'
        }
    else:
        status_message = {
            OrderStatus.PROCESSING: 'is now being processed',
            OrderStatus.SHIPPED: 'has been shipped',
            OrderStatus.DELIVERED: 'has been delivered',
            OrderStatus.CANCELLED: 'has been cancelled'
        }
    
    notification = Notification(
        user_id=recipient_id,
        message=f"Order #{order.order_number} {status_message[new_status]}",
        notification_type='order',
        related_id=order.id
    )
    
    db.session.add(notification)
    db.session.commit()
    
    # Customize flash message based on status and user role
    if current_user.id == order.customer_id and new_status == OrderStatus.DELIVERED:
        flash(f'Order #{order.order_number} has been marked as received. Items have been added to your inventory.', 'success')
    else:
        flash(f'Order status updated from {old_status} to {new_status}.', 'success')
    return redirect(url_for('view_order', order_id=order.id))

# Remove item from order
@app.route('/orders/<int:order_id>/items/<int:item_id>/remove', methods=['POST'])
@login_required
def remove_order_item(order_id, item_id):
    order = Order.query.get_or_404(order_id)
    order_item = OrderItem.query.get_or_404(item_id)
    
    # Ensure the user is the customer and the item belongs to the order
    if order.customer_id != current_user.id or order_item.order_id != order.id:
        flash('You do not have permission to remove this item.', 'warning')
        return redirect(url_for('view_order', order_id=order.id))
    
    # Cannot remove items from orders that are not pending
    if order.status != OrderStatus.PENDING:
        flash('Cannot remove items from orders that are not in the pending state.', 'warning')
        return redirect(url_for('view_order', order_id=order.id))
    
    # Store the item ID and details before deletion
    item_id_to_remove = order_item.id
    
    # Remove the item
    db.session.delete(order_item)
    db.session.flush()
    
    # Update order total (recalculate after removal)
    order.total_amount = sum(item.quantity * item.unit_price for item in order.items)
    
    db.session.commit()
    
    flash('Item removed from order successfully!', 'success')
    return redirect(url_for('view_order', order_id=order.id))

# Notifications route
@app.route('/notifications')
@login_required
def notifications():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Get all notifications for user
    notifications_query = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()
    )
    
    # Paginate results
    notifications_pagination = notifications_query.paginate(page=page, per_page=per_page)
    
    return render_template('notifications/index.html', notifications=notifications_pagination)

# Mark notification as read
@app.route('/notifications/<int:notification_id>/mark_read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    
    # Ensure the notification belongs to the user
    if notification.user_id != current_user.id:
        return jsonify({'success': False}), 403
    
    notification.read = True
    db.session.commit()
    
    # Return JSON response for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    else:
        return redirect(url_for('notifications'))

# Mark all notifications as read
@app.route('/notifications/mark_all_read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, read=False).update({'read': True})
    db.session.commit()
    
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('notifications'))

# Unread notifications count for AJAX endpoint
@app.route('/notifications/unread_count')
@login_required
def unread_notifications_count():
    count = Notification.query.filter_by(user_id=current_user.id, read=False).count()
    return jsonify({'count': count})

# Get product price AJAX endpoint
@app.route('/api/product/<int:product_id>/price')
@login_required
def get_product_price(product_id):
    product = Product.query.get_or_404(product_id)
    return jsonify({'price': product.price})

# User profile route
@app.route('/profile')
@login_required
def profile():
    return render_template(
        'profile.html',
        user=current_user,
        role_name=get_role_display_name(current_user.role)
    )

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('errors/500.html'), 500