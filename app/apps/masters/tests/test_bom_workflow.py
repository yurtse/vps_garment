# apps/masters/tests/test_bom_workflow.py
from django.test import TestCase, RequestFactory
from django.contrib import admin
from django.contrib.auth import get_user_model
from apps.masters.models import Product, Plant, ProductPlant, BOMHeader, BOMItem
from apps.masters import admin as masters_admin



class BOMWorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        # ensure a superuser exists for admin-action test
        self.superuser = User.objects.create_superuser(username="testsu", email="ts@example.com", password="pass")
        # create minimal product/plant/productplant
        self.plant = Plant.objects.create(code="PL1", name="Plant 1")
        self.product = Product.objects.create(code="P-1", name="Product 1", product_group="FG")
        self.pp = ProductPlant.objects.create(product=self.product, plant=self.plant, code="P-1-PL1", name="PP1")
        # make a BOM and one item (component uses same PP for simplicity in this test)
        self.bom = BOMHeader.objects.create(product_plant=self.pp, version=1)
        try:
            # BOMItem field names: component and quantity per project model
            BOMItem.objects.create(bom=self.bom, component=self.pp, quantity=1)
        except Exception:
            # If BOMItem model validation prevents same PP as component, skip item creation here;
            # approve() should still populate header snapshots.
            pass

    def test_approve_sets_fields(self):
        """approve() should set workflow_state, approved_by/at, total snapshot and immutable snapshot."""
        self.assertNotEqual(self.bom.workflow_state, BOMHeader.WorkflowState.APPROVED)
        self.bom.approve(user=self.superuser, total_cost=42.50)
        self.bom.refresh_from_db()
        self.assertEqual(self.bom.workflow_state, BOMHeader.WorkflowState.APPROVED)
        self.assertIsNotNone(self.bom.approved_at)
        self.assertEqual(self.bom.approved_by_id, self.superuser.id)
        self.assertEqual(float(self.bom.total_cost_snapshot), 42.50)
        self.assertTrue(bool(self.bom.immutable_snapshot))

    def test_admin_action_approve_selected_boms(self):
        """Admin action should call approve on selected BOM(s)."""
        # get the registered ModelAdmin instance
        ma = admin.site._registry.get(BOMHeader)
        self.assertIsNotNone(ma, "BOMHeader must be registered in admin for this test")

        # build a fake request with a superuser
        rf = RequestFactory()
        req = rf.post("/")  # method doesn't matter for action invocation
        req.user = self.superuser

        from django.contrib import messages
        # stub out admin.message_user so the test doesn't require MessageMiddleware
        ma.message_user = lambda request, msg, level=messages.INFO: None

        # call the admin action
        # action method name per admin: action_approve_selected_boms
        action_method = getattr(ma, "action_approve_selected_boms", None)
        self.assertIsNotNone(action_method, "approve action must exist on BOMHeaderAdmin")
        # call action with a queryset containing our BOM
        qs = BOMHeader.objects.filter(pk=self.bom.pk)
        # action returns None; it should mutate the BOM
        action_method(req, qs)
        self.bom.refresh_from_db()
        self.assertEqual(self.bom.workflow_state, BOMHeader.WorkflowState.APPROVED)
        self.assertEqual(self.bom.approved_by_id, self.superuser.id)
