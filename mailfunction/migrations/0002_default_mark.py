from django.db import migrations


def create_default(apps, schema_editor):
    MailMark = apps.get_model('mailfunction', 'MailMark')
    if not MailMark.objects.exists():
        MailMark.objects.create(name='重要', symbol='★', color='yellow', sort_order=0)


class Migration(migrations.Migration):

    dependencies = [
        ('mailfunction', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_default, migrations.RunPython.noop),
    ]
