import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('coa', '0001_initial'),
        ('projects', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Contact',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Name')),
                ('phone', models.CharField(blank=True, max_length=50, verbose_name='Phone')),
                ('contact_type', models.CharField(
                    choices=[('vendor', 'Vendor'), ('customer', 'Customer'), ('both', 'Vendor & Customer')],
                    default='vendor', max_length=10, verbose_name='Type',
                )),
                ('is_active', models.BooleanField(default=True, verbose_name='Active')),
                ('advance_account', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='contact_advance_accounts',
                    to='coa.account', verbose_name='Advance Account',
                )),
                ('payable_account', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='contact_payable_accounts',
                    to='coa.account', verbose_name='Payable Account',
                )),
                ('receivable_account', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='contact_receivable_accounts',
                    to='coa.account', verbose_name='Receivable Account',
                )),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='contacts',
                    to='projects.project', verbose_name='Project',
                )),
            ],
            options={
                'verbose_name': 'Contact',
                'verbose_name_plural': 'Contacts',
                'ordering': ['name'],
            },
        ),
    ]
