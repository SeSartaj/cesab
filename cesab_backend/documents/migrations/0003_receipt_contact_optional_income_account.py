from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0002_alter_customerinvoice_exchange_rate_and_more"),
        ("coa", "0002_account_is_tax_account"),
        ("vendors", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="receipt",
            name="contact",
            field=models.ForeignKey(
                blank=True,
                null=True,
                limit_choices_to={"contact_type__in": ["customer", "both"]},
                on_delete=django.db.models.deletion.PROTECT,
                related_name="customer_receipts",
                to="vendors.contact",
                verbose_name="Customer",
            ),
        ),
        migrations.AddField(
            model_name="receipt",
            name="income_account",
            field=models.ForeignKey(
                blank=True,
                null=True,
                help_text="Used when no customer contact is selected (walk-in / one-time payment)",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="walk_in_receipts",
                to="coa.account",
                verbose_name="Income Account",
            ),
        ),
    ]
