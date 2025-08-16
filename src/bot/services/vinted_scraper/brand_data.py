"""Brand-specific item data for mock generation."""

BRAND_ITEMS = {
    'nike': [
        ('Air Max 270', 'Sneakers', ['42', '43', '44']),
        ('Dri-Fit Shirt', 'T-Shirts', ['M', 'L', 'XL']),
        ('Tech Hoodie', 'Hoodies', ['S', 'M', 'L']),
        ('Air Force 1', 'Sneakers', ['41', '42', '43']),
        ('React Element', 'Sneakers', ['40', '41', '42']),
        ('Pro Shorts', 'Shorts', ['M', 'L', 'XL']),
    ],
    'adidas': [
        ('Stan Smith', 'Sneakers', ['41', '42', '43']),
        ('Superstar', 'Sneakers', ['40', '41', '42']),
        ('Ultraboost', 'Sneakers', ['42', '43', '44']),
        ('Trefoil Hoodie', 'Hoodies', ['M', 'L', 'XL']),
        ('3-Stripes Track Pants', 'Trousers', ['M', 'L', 'XL']),
    ],
    'vintage': [
        ('Leather Jacket', 'Jackets', ['M', 'L']),
        ('Denim Jacket', 'Jackets', ['S', 'M', 'L']),
        ('Band T-Shirt', 'T-Shirts', ['M', 'L']),
        ('Wool Sweater', 'Sweaters', ['M', 'L', 'XL']),
    ]
}

DEFAULT_ITEMS = [
    ('Hoodie', 'Hoodies', ['S', 'M', 'L']),
    ('T-Shirt', 'T-Shirts', ['M', 'L', 'XL']),
    ('Jeans', 'Jeans', ['30', '32', '34']),
    ('Sneakers', 'Sneakers', ['41', '42', '43']),
    ('Jacket', 'Jackets', ['M', 'L', 'XL']),
]

PRICE_RANGES = {
    'Sneakers': (25, 120), 'Hoodies': (20, 80), 'T-Shirts': (10, 35),
    'Jackets': (30, 150), 'Jeans': (15, 60), 'Shorts': (12, 40),
    'Sweaters': (18, 70), 'Trousers': (20, 90),
}