from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import CartItem, Category, Order, OrderItem, Product


class StoreBoundaryValueTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="buyer",
            email="buyer@example.com",
            password="StrongerPass123",
        )
        self.category = Category.objects.create(name="Accessories")

    def make_product(self, **overrides):
        values = {
            "name": "Test product",
            "description": "A product for boundary testing.",
            "price": Decimal("10.00"),
            "stock": 1,
            "category": self.category,
        }
        values.update(overrides)
        return Product.objects.create(**values)

    def test_stock_lower_boundary_zero_cannot_be_added_to_cart(self):
        product = self.make_product(stock=0)
        self.client.force_login(self.user)

        response = self.client.get(reverse("add_to_cart", args=[product.id]))

        self.assertRedirects(response, reverse("product_list"))
        self.assertFalse(CartItem.objects.filter(user=self.user, product=product).exists())

    def test_stock_lower_boundary_one_can_be_added_to_cart(self):
        product = self.make_product(stock=1)
        self.client.force_login(self.user)

        response = self.client.get(reverse("add_to_cart", args=[product.id]))

        self.assertRedirects(response, reverse("product_list"))
        self.assertEqual(CartItem.objects.get(user=self.user, product=product).quantity, 1)

    def test_cart_quantity_should_not_exceed_available_stock_boundary(self):
        product = self.make_product(stock=1)
        self.client.force_login(self.user)

        self.client.get(reverse("add_to_cart", args=[product.id]))
        self.client.get(reverse("add_to_cart", args=[product.id]))

        self.assertEqual(CartItem.objects.get(user=self.user, product=product).quantity, 1)

    def test_cart_quantity_lower_boundary_one_is_valid(self):
        product = self.make_product(stock=1)
        cart_item = CartItem(user=self.user, product=product, quantity=1)

        cart_item.full_clean()

    def test_cart_quantity_below_lower_boundary_zero_is_invalid(self):
        product = self.make_product(stock=1)
        cart_item = CartItem(user=self.user, product=product, quantity=0)

        with self.assertRaises(ValidationError):
            cart_item.full_clean()

    def test_product_price_upper_boundary_is_valid(self):
        product = Product(
            name="Boundary price",
            description="Highest valid price for max_digits=10 and decimal_places=2.",
            price=Decimal("99999999.99"),
            stock=1,
            category=self.category,
        )

        product.full_clean()

    def test_product_price_above_upper_boundary_is_invalid(self):
        product = Product(
            name="Too expensive",
            description="One cent above the highest valid price.",
            price=Decimal("100000000.00"),
            stock=1,
            category=self.category,
        )

        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_checkout_empty_cart_boundary_redirects_to_cart(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("checkout"))

        self.assertRedirects(response, reverse("cart"))
        self.assertEqual(Order.objects.count(), 0)

    def test_checkout_single_item_boundary_creates_order_and_clears_cart(self):
        product = self.make_product(stock=1, price=Decimal("12.50"))
        CartItem.objects.create(user=self.user, product=product, quantity=1)
        self.client.force_login(self.user)

        response = self.client.post(reverse("checkout"))

        self.assertRedirects(response, reverse("checkout_success"))
        order = Order.objects.get(user=self.user)
        order_item = OrderItem.objects.get(order=order)
        self.assertEqual(order_item.quantity, 1)
        self.assertEqual(order_item.price, Decimal("12.50"))
        self.assertFalse(CartItem.objects.filter(user=self.user).exists())
