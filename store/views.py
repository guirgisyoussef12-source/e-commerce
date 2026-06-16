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

    products = Product.objects.select_related('category').all()

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

    # ✅ الإصلاح 5 — select_for_update على الـ product والـ cart_item
    # يمنع race condition لو اتنين users حاولوا يضيفوا نفس المنتج في نفس الوقت
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

    total_dollars = sum(item.product.price * item.quantity for item in items)
    total_cents = int(total_dollars * 100)

    # ✅ الإصلاح 1 — إعادة استخدام الـ PaymentIntent الموجود بدل إنشاء واحد جديد كل refresh
    existing_intent_id = request.session.get('pending_intent_id')
    existing_intent_amount = request.session.get('pending_intent_amount')

    intent = None

    if existing_intent_id and existing_intent_amount == total_cents:
        # حاول تجيب الـ intent القديم لو المبلغ لسه نفسه
        try:
            existing_intent = stripe.PaymentIntent.retrieve(existing_intent_id)
            # إعادة استخدام الـ intent بس لو لسه requires_payment_method أو created
            if existing_intent.status in ('requires_payment_method', 'requires_confirmation', 'requires_action'):
                intent = existing_intent
        except stripe.error.StripeError:
            # لو فيه مشكلة في الاسترجاع، هنعمل واحد جديد
            intent = None

    if intent is None:
        # إنشاء PaymentIntent جديد
        intent = stripe.PaymentIntent.create(
            amount=total_cents,
            currency='usd',
            metadata={
                'user_id': str(request.user.id),
                'user_email': request.user.email,
            },
        )
        request.session['pending_intent_id'] = intent.id
        request.session['pending_intent_amount'] = total_cents

    return render(request, 'store/checkout.html', {
        'items': items,
        'total': total_dollars,
        'client_secret': intent.client_secret,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
    })


@login_required
@require_POST
def payment_confirm(request):
    payment_intent_id = request.POST.get('payment_intent_id')
    if not payment_intent_id:
        return redirect('checkout')

    # منع الـ Double Spend
    if Order.objects.filter(stripe_payment_intent=payment_intent_id).exists():
        return redirect('checkout_success')

    # تأكد إن الـ intent بتاع الـ user ده تحديداً من الـ session
    expected_intent_id = request.session.get('pending_intent_id')
    if not expected_intent_id or payment_intent_id != expected_intent_id:
        return redirect('checkout')

    # تحقق من Stripe
    try:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
    except stripe.error.StripeError as e:
        logger.error(f'Stripe retrieve error for user {request.user.id}: {e}')
        return redirect('checkout')

    if intent.status != 'succeeded':
        return redirect('checkout')

    # تحقق من الـ metadata إن الـ user_id صح
    if intent.metadata.get('user_id') != str(request.user.id):
        logger.warning(f'Intent user_id mismatch for user {request.user.id}')
        return redirect('checkout')

    # جيب الـ cart
    items = CartItem.objects.filter(user=request.user).select_related('product')
    if not items.exists():
        return redirect('cart')

    # ✅ الإصلاح 2 — استخدام pending_intent_amount كـ consistency check
    # بدل إعادة حساب الـ total من الـ DB (اللي ممكن يكون اتغير)
    # بنتحقق إن الـ intent amount يطابق اللي خزناه في الـ session وقت إنشاء الـ intent
    stored_amount = request.session.get('pending_intent_amount')
    if not stored_amount or intent.amount != stored_amount:
        # المبلغ اتغير — ارجع للـ checkout لإنشاء intent جديد
        request.session.pop('pending_intent_id', None)
        request.session.pop('pending_intent_amount', None)
        return redirect('checkout')

    # ✅ الإصلاح 3 — Exception handling جوه الـ transaction مع graceful error page
    try:
        with transaction.atomic():
            locked_products = Product.objects.select_for_update().filter(
                id__in=items.values_list('product_id', flat=True)
            )
            stock_map = {p.id: p for p in locked_products}

            # تحقق من الـ stock بعد القفل
            for item in items:
                product = stock_map[item.product_id]
                if product.stock < item.quantity:
                    # المنتج خلص — لازم نعمل refund
                    # في production: استدعي stripe.Refund.create هنا
                    logger.error(
                        f'Stock insufficient after payment for user {request.user.id}, '
                        f'product {item.product_id}. Manual refund needed for intent {payment_intent_id}.'
                    )
                    return render(request, 'store/payment_error.html', {
                        'message': 'Sorry, an item in your order just went out of stock. '
                                   'Your payment will be refunded within 3-5 business days.',
                        'intent_id': payment_intent_id,
                    }, status=200)

            order = Order.objects.create(
                user=request.user,
                stripe_payment_intent=payment_intent_id,
                payment_status='paid',
                complete=True,
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
        logger.exception(f'Unexpected error in payment_confirm for user {request.user.id}: {e}')
        return render(request, 'store/payment_error.html', {
            'message': 'Something went wrong while processing your order. '
                       'Your payment was received — our team has been notified and will contact you shortly.',
            'intent_id': payment_intent_id,
        }, status=500)

    # امسح الـ session بعد الاستخدام
    request.session.pop('pending_intent_id', None)
    request.session.pop('pending_intent_amount', None)

    # ✅ الإصلاح 4 — خزن الـ order ID في الـ session عشان checkout_success يعرضه
    request.session['last_order_id'] = order.id

    return redirect('checkout_success')


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

    if event['type'] == 'payment_intent.succeeded':
        intent = event['data']['object']
        with transaction.atomic():
            Order.objects.select_for_update().filter(
                stripe_payment_intent=intent['id']
            ).update(payment_status='paid', complete=True)

    elif event['type'] == 'payment_intent.payment_failed':
        intent = event['data']['object']
        with transaction.atomic():
            Order.objects.select_for_update().filter(
                stripe_payment_intent=intent['id']
            ).update(payment_status='failed')

    return HttpResponse(status=200)


@login_required
def checkout_success(request):
    # ✅ الإصلاح 4 — عرض الـ order اللي اتعمل للتو بس من الـ session
    order_id = request.session.pop('last_order_id', None)

    if not order_id:
        # مفيش order في الـ session — redirect للـ orders page
        return redirect('order_history')

    order = get_object_or_404(
        Order.objects.prefetch_related('items__product'),
        id=order_id,
        user=request.user,
        payment_status='paid',
    )

    return render(request, 'store/checkout_success.html', {'order': order})


@login_required
def order_history(request):
    orders = Order.objects.filter(
        user=request.user
    ).prefetch_related('items__product').order_by('-created_at')
    return render(request, 'store/order_history.html', {'orders': orders})