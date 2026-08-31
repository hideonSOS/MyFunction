# 手動並び順(sort_order)の初期値を、従来の表示順（未完了→重要度降順→更新降順）で
# 振り直すデータマイグレーション。これにより導入直後も見た目の並びが変わらない。
from django.db import migrations


def init_sort_order(apps, schema_editor):
    TodoItem = apps.get_model('todo', 'TodoItem')
    user_ids = TodoItem.objects.values_list('user_id', flat=True).distinct()
    for uid in user_ids:
        items = (TodoItem.objects.filter(user_id=uid)
                 .order_by('done', '-importance', '-updated'))
        for i, item in enumerate(items):
            item.sort_order = i
        TodoItem.objects.bulk_update(items, ['sort_order'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('todo', '0003_alter_todoitem_options_todoitem_sort_order'),
    ]

    operations = [
        migrations.RunPython(init_sort_order, noop),
    ]
