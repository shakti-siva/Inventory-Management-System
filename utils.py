import random
import string
from datetime import datetime
from models import Role

def generate_order_number():
    """Generate a unique order number with format YYMMDDxxxx where xxxx is random."""
    today = datetime.now()
    date_part = today.strftime('%y%m%d')
    # Using both timestamp microseconds and random digits to ensure uniqueness
    timestamp_part = str(int(datetime.now().timestamp() * 1000))[-4:]
    random_part = ''.join(random.choices(string.digits, k=4))
    return f"{date_part}{timestamp_part}{random_part}"

def can_view_product(user, product):
    """Check if a user can view a product."""
    if user.role == Role.MANUFACTURER:
        # Manufacturers can view all products
        return True
    elif user.role == Role.WHOLESALER:
        # Wholesalers can view products from manufacturers and their own
        return True
    elif user.role == Role.RETAILER:
        # Retailers can view products from wholesalers and manufacturers
        return True
    else:  # Customer
        # Customers can only view products from retailers
        return True
    
    return False

def can_edit_product(user, product):
    """Check if a user can edit a product."""
    if user.role == Role.MANUFACTURER:
        # Only manufacturers can edit products
        return True
    return False

def can_delete_product(user, product):
    """Check if a user can delete a product."""
    if user.role == Role.MANUFACTURER:
        # Only manufacturers can delete products
        return True
    return False

def get_role_display_name(role):
    """Convert role code to display name."""
    if role == Role.CUSTOMER:
        return "Customer"
    elif role == Role.RETAILER:
        return "Retailer"
    elif role == Role.WHOLESALER:
        return "Wholesaler"
    elif role == Role.MANUFACTURER:
        return "Manufacturer"
    return role