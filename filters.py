from app import app
from models import ProductCategory, ProductGender

# Filter to format product categories
@app.template_filter('format_category')
def format_category(category):
    if category == ProductCategory.TSHIRT:
        return 'T-Shirt'
    elif category == ProductCategory.SHOES:
        return 'Shoes'
    elif category == ProductCategory.ACCESSORIES:
        return 'Accessories'
    elif category == ProductCategory.DRESS:
        return 'Dress'
    return category or 'N/A'

# Filter to format product gender
@app.template_filter('format_gender')
def format_gender(gender):
    if gender == ProductGender.MENS:
        return "Men's"
    elif gender == ProductGender.WOMENS:
        return "Women's"
    elif gender == ProductGender.UNISEX:
        return "Unisex"
    return gender or 'N/A'

# Filter to format product attributes that might be None
@app.template_filter('product_attr')
def product_attr(value):
    return value if value else 'N/A'