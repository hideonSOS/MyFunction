# 名簿の初期データ投入。従来 haichi.js に直書きされていた12名と色をそのまま移す。
# （これにより既存の配置データ・色との互換を保つ）
from django.db import migrations

SEED = [
    ('松山', 'c1'),  ('清水', 'c2'),  ('生田', 'c3'),  ('栗原', 'c4'),
    ('芳松', 'c5'),  ('水野', 'c6'),  ('表木', 'c7'),  ('虎谷', 'c8'),
    ('小林', 'c9'),  ('三室', 'c10'), ('金山', 'c11'), ('山田', 'c12'),
]


def seed(apps, schema_editor):
    LayoutMember = apps.get_model('nitei', 'LayoutMember')
    if LayoutMember.objects.exists():
        return
    LayoutMember.objects.bulk_create([
        LayoutMember(name=n, color=c, order=i) for i, (n, c) in enumerate(SEED)
    ])


def unseed(apps, schema_editor):
    apps.get_model('nitei', 'LayoutMember').objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ('nitei', '0011_layoutmember'),
    ]
    operations = [
        migrations.RunPython(seed, unseed),
    ]
