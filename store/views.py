from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Product, CartItem, Order, OrderItem , Category
from django.db import transaction
def home(request):
    if request.user.is_authenticated:
        return redirect('product_list')
    return redirect('sign_up')


@login_required
def product_list(request):
    query = request.GET.get('q')
    category_id = request.GET.get('category')

    products = Product.objects.all()

    if query:
        products = products.filter(name__icontains=query)
    if category_id:
        products = products.filter(category_id=category_id)

    categories = Category.objects.all()
    return render(request, 'store/products.html', {
        'products': products,
        'categories': categories 
    })


@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method != 'POST':
        return redirect('product_list')
    if product.stock == 0:
        return redirect('product_list')

    cart_item, created = CartItem.objects.get_or_create(
        user=request.user,
        product=product,
        defaults={'quantity': 1}
    )

    if not created and cart_item.quantity < product.stock:
        cart_item.quantity += 1
        cart_item.save()

    return redirect('product_list')


@login_required
def cart_view(request):
    items = CartItem.objects.filter(user=request.user).select_related('product')
    return render(request, 'store/cart.html', {'items': items})


@login_required
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, user=request.user)
    item.delete()
    return redirect('cart')


@login_required
def checkout(request):
    items = CartItem.objects.filter(user=request.user)

    if not items.exists():
        return redirect('cart')

    if request.method == 'POST':
        with transaction.atomic():
            order = Order.objects.create(user=request.user)

            for item in items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )
                item.product.stock -= item.quantity
                item.product.save()
        items.delete()

        return redirect('checkout_success')

    total = sum(item.product.price * item.quantity for item in items)

    return render(request, 'store/checkout.html', {
        'items': items,
        'total': total
    })


@login_required
def checkout_success(request):
    return render(request, 'store/checkout_success.html')
@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).prefetch_related('items__product').order_by('-created_at')
    return render(request, 'store/order_history.html', {'orders': orders})