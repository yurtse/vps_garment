# tools/inspect_productplant_counts.py
import django
django.setup()
from apps.masters.models import ProductPlant, Product

print("Total ProductPlant rows:", ProductPlant.objects.count())
print("Per-product counts (first 50 products):")
for p in Product.objects.all()[:50]:
    print(f"  Product {p.pk} ({getattr(p,'code',None)}) -> {ProductPlant.objects.filter(product=p).count()}")
