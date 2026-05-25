from django.urls import path
from .views import (
    ProductListCreateView,
    ProductDetailView,
    CategoryListCreateView,
    CartView,
    CartItemDeleteView,
    CheckoutView,
    OrderHistoryView,
)

urlpatterns = [
    path('products/', ProductListCreateView.as_view()),
    path('products/<int:pk>/', ProductDetailView.as_view()),
    path('categories/', CategoryListCreateView.as_view()),
    path('cart/', CartView.as_view()),
    path('cart/<int:item_id>/', CartItemDeleteView.as_view()),
    path('checkout/', CheckoutView.as_view()),
    path('orders/', OrderHistoryView.as_view()),
]