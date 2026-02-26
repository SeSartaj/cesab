from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0002_remove_role_add_projectmember'),
    ]

    operations = [
        migrations.AlterField(
            model_name='projectmember',
            name='role',
            field=models.CharField(
                choices=[('admin', 'Admin'), ('accountant', 'Accountant'), ('viewer', 'Viewer')],
                default='viewer',
                max_length=20,
                verbose_name='Role',
            ),
        ),
    ]
