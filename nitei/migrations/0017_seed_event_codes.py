from django.db import migrations

# これまで画面に固定で書かれていた区分（クリック順・色・公休数の数え方を引き継ぐ）
INITIAL_CODES = [
    ('公開FM',   'white',  'work'),
    ('FM臨時',   'white',  'work'),
    ('本社',     'white',  'work'),
    ('公休',     'orange', 'holiday'),
    ('指定公休', 'red',    'holiday'),
    ('有給',     'orange', 'rest'),
]


def seed(apps, schema_editor):
    EventCode = apps.get_model('nitei', 'EventCode')
    if EventCode.objects.exists():
        return
    for order, (name, color, kind) in enumerate(INITIAL_CODES):
        EventCode.objects.create(name=name, color=color, kind=kind, order=order)


class Migration(migrations.Migration):

    dependencies = [
        ('nitei', '0016_eventcode'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
