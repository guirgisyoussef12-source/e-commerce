from django.contrib import admin

from .models import CartItem, Category, Order, OrderItem, Product

admin.site.register(Category)
admin.site.register(Product)
admin.site.register(OrderItem)
admin.site.register(Order)
admin.site.register(CartItem)
