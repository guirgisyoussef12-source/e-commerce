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
    
    # التحقق من وجود مخزون أصلاً
    if product.stock == 0:
        return redirect('product_list')

    # 1. قراءة الكمية المطلوبة (سواء مبعوتة POST أو GET ليتوافق مع الـ Tests)
    if request.method == 'POST':
        try:
            requested_quantity = int(request.POST.get('quantity', 1))
        except ValueError:
            requested_quantity = 1
    else:
        try:
            requested_quantity = int(request.GET.get('quantity', 1))
        except ValueError:
            requested_quantity = 1

    # 2. جلب أو إنشاء الـ CartItem بـ quantity=0 للحساب الدقيق والآمن للـ Boundaries
    cart_item, created = CartItem.objects.get_or_create(
        user=request.user,
        product=product,
        defaults={'quantity': 0}
    )

    # 3. حساب الإجمالي المستهدف الجديد في العربة
    new_quantity = cart_item.quantity + requested_quantity

    # 4. تطبيق شروط الـ Boundary (القيم الحدية)
    if new_quantity <= product.stock:
        cart_item.quantity = new_quantity
        cart_item.save()
    else:
        # لو الطلب الجديد عدا المتاح، بنثبت الكمية عند الحد الأقصى للمخزون (الـ Stock كله)
        cart_item.quantity = product.stock
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

        for item in items:
            if item.product.stock < item.quantity:
                return redirect('cart')

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