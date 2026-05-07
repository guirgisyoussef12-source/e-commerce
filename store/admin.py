from django.contrib import admin
from .models import Category, Product, OrderItem, Order, CartItem
admin.site.register(Category)
admin.site.register(Product)
admin.site.register(OrderItem)
admin.site.register(Order)
admin.site.register(CartItem)
