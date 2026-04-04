import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0001_initial"),
        ("vendors", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="inventorymovement",
            name="contact",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="inventory_movements",
                to="vendors.contact",
                verbose_name="Contact",
                help_text="Contact for cash-to-vendor purchases",
            ),
        ),
    ]
