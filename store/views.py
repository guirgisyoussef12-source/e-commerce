import logging

import stripe
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import transaction

from .models import Product, CartItem, Order, OrderItem, Category

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)


def home(request):
    if request.user.is_authenticated:
        return redirect('product_list')
    return redirect('sign_up')


@login_required
def product_list(request):
    query = request.GET.get('q')
    category_id = request.GET.get('category')

    products = Product.objects.select_related('category').all().order_by('id')

    if query:
        products = products.filter(name__icontains=query)
    if category_id:
        products = products.filter(category_id=category_id)

    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.all()
    return render(request, 'store/products.html', {
        'products': page_obj,
        'page_obj': page_obj,
        'categories': categories,
    })


@login_required
@require_POST
def add_to_cart(request, product_id):
    try:
        requested_quantity = int(request.POST.get('quantity', 1))
    except ValueError:
        requested_quantity = 1

    requested_quantity = max(1, requested_quantity)

    with transaction.atomic():
        product = get_object_or_404(
            Product.objects.select_for_update(),
            id=product_id
        )

        if product.stock == 0:
            return redirect('product_list')

        cart_item, created = CartItem.objects.select_for_update().get_or_create(
            user=request.user,
            product=product,
            defaults={'quantity': 0}
        )

        new_quantity = cart_item.quantity + requested_quantity
        cart_item.quantity = min(new_quantity, product.stock)
        cart_item.save()

    return redirect('product_list')


@login_required
def cart_view(request):
    items = CartItem.objects.filter(user=request.user).select_related('product')
    return render(request, 'store/cart.html', {'items': items})


@login_required
@require_POST
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, user=request.user)
    item.delete()
    return redirect('cart')


@login_required
def checkout(request):
    items = CartItem.objects.filter(user=request.user).select_related('product')

    if not items.exists():
        return redirect('cart')

    # بناء line_items لـ Stripe Checkout
    line_items = []
    for item in items:
        line_items.append({
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': item.product.name,
                    'description': item.product.description[:100] if item.product.description else '',
                },
                'unit_amount': int(item.product.price * 100),
            },
            'quantity': item.quantity,
        })

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            # ✅ بيجمع العنوان ويسمح بـ US بس
            shipping_address_collection={
                'allowed_countries': ['US'],
            },
            shipping_options=[
                {
                    'shipping_rate_data': {
                        'type': 'fixed_amount',
                        'fixed_amount': {'amount': 500, 'currency': 'usd'},
                        'display_name': 'Standard shipping (3–5 business days)',
                        'delivery_estimate': {
                            'minimum': {'unit': 'business_day', 'value': 3},
                            'maximum': {'unit': 'business_day', 'value': 5},
                        },
                    },
                },
                {
                    'shipping_rate_data': {
                        'type': 'fixed_amount',
                        'fixed_amount': {'amount': 1500, 'currency': 'usd'},
                        'display_name': 'Express shipping (1–2 business days)',
                        'delivery_estimate': {
                            'minimum': {'unit': 'business_day', 'value': 1},
                            'maximum': {'unit': 'business_day', 'value': 2},
                        },
                    },
                },
            ],
            customer_email=request.user.email,
            success_url=request.build_absolute_uri('/checkout/success/') + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.build_absolute_uri('/cart/'),
            metadata={
                'user_id': str(request.user.id),
                'user_email': request.user.email,
            },
        )
    except stripe.error.StripeError as e:
        logger.error(f'Stripe session creation error for user {request.user.id}: {e}')
        return render(request, 'store/payment_error.html', {
            'message': 'Unable to connect to payment provider. Please try again.',
            'intent_id': '',
        })

    # خزن الـ session ID عشان نتحقق منه في الـ success
    request.session['stripe_checkout_session_id'] = session.id

    return redirect(session.url, permanent=False)


@login_required
def checkout_success(request):
    session_id = request.GET.get('session_id')

    if not session_id:
        return redirect('order_history')

    # تحقق إن الـ session_id بتاع الـ user ده فعلاً
    stored_session_id = request.session.get('stripe_checkout_session_id')
    if session_id != stored_session_id:
        logger.warning(f'Session ID mismatch for user {request.user.id}')
        return redirect('order_history')

    # لو الـ order اتعمل قبل كده (webhook سبق) — روح عليه مباشرة
    existing_order = Order.objects.filter(
        stripe_payment_intent=session_id,
        user=request.user,
    ).prefetch_related('items__product').first()

    if existing_order:
        request.session.pop('stripe_checkout_session_id', None)
        return render(request, 'store/checkout_success.html', {'order': existing_order})

    # تحقق من Stripe إن الدفع اتم فعلاً
    try:
        session = stripe.checkout.Session.retrieve(
            session_id,
            expand=['line_items', 'shipping_details'],
        )
    except stripe.error.StripeError as e:
        logger.error(f'Stripe session retrieve error for user {request.user.id}: {e}')
        return redirect('order_history')

    if session.payment_status != 'paid':
        return redirect('cart')

    # تحقق إن الـ user_id في الـ metadata صح
    if session.metadata.get('user_id') != str(request.user.id):
        logger.warning(f'Stripe session user_id mismatch for user {request.user.id}')
        return redirect('order_history')

    items = CartItem.objects.filter(user=request.user).select_related('product')

    if not items.exists():
        return redirect('order_history')

    # استخرج عنوان التوصيل من Stripe
    shipping = session.shipping_details
    shipping_address = ''
    if shipping and shipping.address:
        addr = shipping.address
        shipping_address = f"{shipping.name}, {addr.line1}, {addr.city}, {addr.state} {addr.postal_code}, {addr.country}"

    try:
        with transaction.atomic():
            locked_products = Product.objects.select_for_update().filter(
                id__in=items.values_list('product_id', flat=True)
            )
            stock_map = {p.id: p for p in locked_products}

            for item in items:
                product = stock_map[item.product_id]
                if product.stock < item.quantity:
                    logger.error(
                        f'Stock insufficient after payment for user {request.user.id}, '
                        f'product {item.product_id}. Stripe session: {session_id}'
                    )
                    return render(request, 'store/payment_error.html', {
                        'message': 'Sorry, an item in your order just went out of stock. '
                                   'Your payment will be refunded within 3-5 business days.',
                        'intent_id': session_id,
                    })

            order = Order.objects.create(
                user=request.user,
                stripe_payment_intent=session_id,
                payment_status='paid',
                complete=True,
                shipping_address=shipping_address,
            )

            for item in items:
                product = stock_map[item.product_id]
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=item.quantity,
                    price=product.price,
                )
                product.stock -= item.quantity
                product.save(update_fields=['stock'])

            items.delete()

    except Exception as e:
        logger.exception(f'Unexpected error in checkout_success for user {request.user.id}: {e}')
        return render(request, 'store/payment_error.html', {
            'message': 'Something went wrong while processing your order. '
                       'Your payment was received — our team has been notified.',
            'intent_id': session_id,
        })

    request.session.pop('stripe_checkout_session_id', None)

    return render(request, 'store/checkout_success.html', {'order': order})


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET

    if not webhook_secret:
        logger.error('STRIPE_WEBHOOK_SECRET is not configured')
        return HttpResponse('Webhook secret not configured', status=500)

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        logger.warning('Invalid Stripe webhook signature')
        return HttpResponse(status=400)

    # Stripe Checkout events
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        with transaction.atomic():
            Order.objects.select_for_update().filter(
                stripe_payment_intent=session['id']
            ).update(payment_status='paid', complete=True)

    elif event['type'] == 'checkout.session.expired':
        session = event['data']['object']
        logger.info(f'Checkout session expired: {session["id"]}')

    return HttpResponse(status=200)


@login_required
def order_history(request):
    orders = Order.objects.filter(
        user=request.user
    ).prefetch_related('items__product').order_by('-created_at')
    return render(request, 'store/order_history.html', {'orders': orders})