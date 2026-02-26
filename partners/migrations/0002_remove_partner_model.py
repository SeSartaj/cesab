# Migration: replace Partner FK with direct User FK on ProjectPartner,
# then drop the Partner model entirely.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrate_partner_to_user(apps, schema_editor):
    """
    For every ProjectPartner, copy partner.user -> user.
    Delete ProjectPartner rows whose partner has no linked user (can't migrate).
    """
    ProjectPartner = apps.get_model("partners", "ProjectPartner")
    to_delete = []
    to_update = []
    for pp in ProjectPartner.objects.select_related("partner").all():
        if pp.partner.user_id is None:
            to_delete.append(pp.pk)
        else:
            pp.user_id = pp.partner.user_id
            to_update.append(pp)
    ProjectPartner.objects.filter(pk__in=to_delete).delete()
    for pp in to_update:
        pp.save(update_fields=["user_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("coa", "0001_initial"),
        ("partners", "0001_initial"),
        ("projects", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Add a nullable user FK to ProjectPartner
        migrations.AddField(
            model_name="projectpartner",
            name="user",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="project_participations",
                to=settings.AUTH_USER_MODEL,
                verbose_name="User",
            ),
        ),
        # 2. Populate user from partner.user; drop rows that have no user
        migrations.RunPython(migrate_partner_to_user, migrations.RunPython.noop),
        # 3. Clear old unique_together before removing partner field
        migrations.AlterUniqueTogether(
            name="projectpartner",
            unique_together=set(),
        ),
        # 4. Drop the old partner FK
        migrations.RemoveField(
            model_name="projectpartner",
            name="partner",
        ),
        # 5. Make user non-nullable
        migrations.AlterField(
            model_name="projectpartner",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="project_participations",
                to=settings.AUTH_USER_MODEL,
                verbose_name="User",
            ),
        ),
        # 6. Restore unique_together with (project, user)
        migrations.AlterUniqueTogether(
            name="projectpartner",
            unique_together={("project", "user")},
        ),
        # 7. Delete the Partner model
        migrations.DeleteModel(
            name="Partner",
        ),
    ]
