from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from .models import (
    Supplier, Product, ProductVariant, StockItem, StockAdjustment,
    Service, Invoice, InvoiceItem, InvoicePayment, Refund,
    PurchaseOrder, PurchaseOrderItem, SupplierPayment, PurchaseReturn, 
    SupplierRefund, SupplierCredit, CreditApplication
)

class BasicBillingModelTests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(name="Test Supplier", category="LOCAL_SHOP")
        self.product = Product.objects.create(name="Test Product", category="CONSUMABLES", is_stockable=True, is_active=True)
        self.variant = ProductVariant.objects.create(product=self.product, price=100, is_active=True)
        self.service = Service.objects.create(name="Test Service", price=500)
    
    def test_supplier_created(self):
        self.assertEqual(str(self.supplier), "Test Supplier")
    
    def test_product_variant_stock(self):
        self.assertEqual(self.variant.stock_quantity, 0)

    def test_service_created(self):
        self.assertTrue(self.service.is_active)

class SupplierCreditFeatureTests(TestCase):
    def setUp(self):
        """Set up the necessary objects for testing the credit feature."""
        self.supplier = Supplier.objects.create(name="Test Supplier Inc.", category="LOCAL_DISTRIBUTOR")
        self.product = Product.objects.create(name="Test Meds", category="DRUGS")
        self.variant = ProductVariant.objects.create(product=self.product, price=15)
        self.user = User.objects.create_user('tester', 'tester@test.com', 'password')

        # Create a completed PO to generate a credit from
        self.po1 = PurchaseOrder.objects.create(supplier=self.supplier)
        self.po1_item = PurchaseOrderItem.objects.create(purchase_order=self.po1, product_variant=self.variant, quantity=100)
        self.stock_item1 = StockItem.objects.create(
            product_variant=self.variant,
            purchase_order_item=self.po1_item,
            supplier=self.supplier,
            quantity=100,
            cost_price=Decimal('10.00'),
            batch_number="BATCH001"
        )
        self.po1_item.quantity_received = 100
        self.po1_item.save()
        self.po1.update_status()

    def test_credit_creation_on_refund(self):
        """Test that a SupplierCredit is automatically created when a SupplierRefund is saved."""
        self.assertEqual(SupplierCredit.objects.count(), 0)

        # Return 20 items from the stock
        return_instance = PurchaseReturn.objects.create(
            stock_item=self.stock_item1,
            quantity=20,
            purchase_order=self.po1
        )
        # Issue a refund for these 20 items
        refund_instance = SupplierRefund.objects.create(
            purchase_return=return_instance,
            amount=Decimal('200.00') # 20 items * 10.00 cost price
        )

        # Check that the signal created a credit
        self.assertEqual(SupplierCredit.objects.count(), 1)
        credit = SupplierCredit.objects.first()
        self.assertEqual(credit.supplier, self.supplier)
        self.assertEqual(credit.source_refund, refund_instance)
        self.assertEqual(credit.initial_amount, Decimal('200.00'))
        self.assertEqual(credit.balance, Decimal('200.00'))

    def test_credit_application_and_balance_updates(self):
        """Test applying a credit to a new PO and verify all balances update correctly."""
        # First, create a credit note by simulating a refund
        return_instance = PurchaseReturn.objects.create(stock_item=self.stock_item1, quantity=20, purchase_order=self.po1)
        SupplierRefund.objects.create(purchase_return=return_instance, amount=Decimal('200.00'))
        
        credit = SupplierCredit.objects.first()
        self.assertIsNotNone(credit)

        # Create a new PO that needs payment
        po2 = PurchaseOrder.objects.create(supplier=self.supplier)
        po2_item = PurchaseOrderItem.objects.create(purchase_order=po2, product_variant=self.variant, quantity=50)
        StockItem.objects.create(
            product_variant=self.variant, purchase_order_item=po2_item, supplier=self.supplier,
            quantity=50, cost_price=Decimal('10.00'), batch_number="BATCH002"
        )
        po2_item.quantity_received = 50
        po2_item.save()
        po2.update_status()

        self.assertEqual(po2.grand_total, Decimal('500.00'))
        self.assertEqual(po2.balance_due, Decimal('500.00'))

        # Apply the credit to the new PO
        CreditApplication.objects.create(
            credit=credit,
            applied_to_po=po2,
            amount_applied=Decimal('150.00')
        )

        # Refresh objects from DB to get updated values
        credit.refresh_from_db()
        po2.refresh_from_db()

        # Verify balances
        self.assertEqual(credit.balance, Decimal('50.00')) # 200 - 150 = 50
        self.assertFalse(credit.is_fully_used)
        self.assertEqual(po2.amount_credited, Decimal('150.00'))
        self.assertEqual(po2.balance_due, Decimal('350.00')) # 500 - 150 = 350