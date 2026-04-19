from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, SelectField, IntegerField, TextAreaField, HiddenField, FloatField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, NumberRange
from models import User, Role, ProductCategory, ProductGender

# Registration form
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Role', validators=[DataRequired()], 
                      choices=[(Role.CUSTOMER, 'Customer'), 
                               (Role.RETAILER, 'Retailer'), 
                               (Role.WHOLESALER, 'Wholesaler'), 
                               (Role.MANUFACTURER, 'Manufacturer')])
    company_name = StringField('Company Name (Optional)', validators=[Length(max=100)])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already exists. Please choose a different one.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please use a different one.')

# Login form
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

# Product form
class ProductForm(FlaskForm):
    name = StringField('Product Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description')
    sku = StringField('SKU', validators=[DataRequired(), Length(max=50)])
    category = SelectField('Category', validators=[DataRequired()])
    size = StringField('Size', validators=[Length(max=20)])
    color = StringField('Color', validators=[Length(max=30)])
    pattern = StringField('Pattern', validators=[Length(max=50)])
    gender = SelectField('Gender', validators=[DataRequired()])
    price = FloatField('Price', validators=[DataRequired(), NumberRange(min=0)])
    image = FileField('Product Image', validators=[FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Images only!')])
    submit = SubmitField('Save Product')
    
    def validate_sku(self, sku):
        from app import db
        from models import Product
        
        # Only validate SKU uniqueness if provided (SKU can be generated automatically)
        if not sku.data:
            return
            
        # When editing an existing product, we need to exclude the current product's SKU
        product_id = self.product_id if hasattr(self, 'product_id') else None
        
        # Check if this SKU exists
        product = Product.query.filter_by(sku=sku.data).first()
        if product and (not product_id or product.id != product_id):
            raise ValidationError('This SKU is already in use. Please use a unique SKU.')

    def __init__(self, *args, **kwargs):
        super(ProductForm, self).__init__(*args, **kwargs)
        # Set category choices
        self.category.choices = [
            (ProductCategory.TSHIRT, 'T-Shirt'),
            (ProductCategory.SHOES, 'Shoes'),
            (ProductCategory.ACCESSORIES, 'Accessories'),
            (ProductCategory.DRESS, 'Dress')
        ]
        # Set gender choices
        self.gender.choices = [
            (ProductGender.MENS, "Men's"),
            (ProductGender.WOMENS, "Women's"),
            (ProductGender.UNISEX, 'Unisex')
        ]

# Inventory form
class InventoryForm(FlaskForm):
    product_id = HiddenField('Product ID', validators=[DataRequired()])
    quantity = IntegerField('Quantity', validators=[DataRequired(), NumberRange(min=0)])
    min_stock_level = IntegerField('Minimum Stock Level', validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField('Update Inventory')

# Order form
class OrderForm(FlaskForm):
    supplier_id = SelectField('Supplier', validators=[DataRequired()], coerce=int)
    customer_notes = TextAreaField('Notes to Supplier')
    submit = SubmitField('Create Order')

# Order item form
class OrderItemForm(FlaskForm):
    product_id = SelectField('Product', validators=[DataRequired()], coerce=int)
    quantity = IntegerField('Quantity', validators=[DataRequired(), NumberRange(min=1)])
    unit_price = FloatField('Unit Price', validators=[])
    submit = SubmitField('Add to Order')