from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver


class TodoItem(models.Model):
    """進捗確認ToDo。重要度の降順で並べるメモ書きリスト"""
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name='todo_items')
    title      = models.CharField(max_length=200)
    memo       = models.TextField(blank=True)                 # 詳細（リッチテキストHTML）
    importance = models.PositiveSmallIntegerField(default=3)  # 1〜5（5=最重要）
    progress   = models.PositiveSmallIntegerField(default=0)  # 0〜100 (%)
    done       = models.BooleanField(default=False)
    # 手動の並び順（小さいほど上）。一覧のドラッグ&ドロップで更新される。
    # 新規は既存の最小値-1（=先頭）に置く
    sort_order = models.IntegerField(default=0)
    created    = models.DateTimeField(auto_now_add=True)
    updated    = models.DateTimeField(auto_now=True)

    class Meta:
        # 未完了が上 → 手動順。重要度・更新日は手動順が同値のときのタイブレーク
        ordering = ['done', 'sort_order', '-importance', '-updated']

    def __str__(self):
        return f'[★{self.importance} {self.progress}%] {self.title}'


def todo_attachment_path(instance, filename):
    """ToDoごとにフォルダ分けして保存する（media/todo/item/<id>/<file>）"""
    return f'todo/item/{instance.item_id}/{filename}'


class TodoAttachment(models.Model):
    """ToDoに添付するファイル（スクリーンショット等の画像・PDF）。付箋と同方式"""
    item         = models.ForeignKey(TodoItem, on_delete=models.CASCADE,
                                     related_name='attachments')
    file         = models.FileField(upload_to=todo_attachment_path)
    name         = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)
    size         = models.PositiveIntegerField(default=0)
    order        = models.IntegerField(default=0)
    uploaded     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'uploaded', 'id']

    def __str__(self):
        return self.name

    @property
    def is_image(self):
        return self.content_type.startswith('image/')

    @property
    def is_pdf(self):
        return self.content_type == 'application/pdf'


@receiver(post_delete, sender=TodoAttachment)
def _delete_todo_attachment_file(sender, instance, **kwargs):
    """レコード削除時に実ファイルもディスクから消す（ToDo削除のカスケード含む）"""
    if instance.file:
        instance.file.delete(save=False)
