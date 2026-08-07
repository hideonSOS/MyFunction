from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone


# 付箋・タスク共通の色パレット（実際の色は CSS の .tone-* で定義）
TONE_CHOICES = [
    ('yellow', 'イエロー'),
    ('pink',   'ピンク'),
    ('green',  'グリーン'),
    ('blue',   'ブルー'),
    ('purple', 'パープル'),
    ('gray',   'グレー'),
]


class Note(models.Model):
    """付箋（自由メモ）。ボードにピン留めして貼っておく"""
    user     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name='notes')
    title    = models.CharField(max_length=200, blank=True)  # 見出し
    body     = models.TextField(blank=True)                  # 中身
    tone     = models.CharField(max_length=10, choices=TONE_CHOICES, default='yellow')
    pinned   = models.BooleanField(default=False)
    archived = models.BooleanField(default=False)
    date     = models.DateField(null=True, blank=True)  # カレンダー上の配置日（未設定=未分類）
    time     = models.TimeField(null=True, blank=True)  # 時間軸上の配置時刻（未設定=終日）
    order    = models.IntegerField(default=0)          # ボード内の並び順
    created  = models.DateTimeField(auto_now_add=True)
    updated  = models.DateTimeField(auto_now=True)

    class Meta:
        # ピン留め優先 → 手動並び順 → 新しい順
        ordering = ['-pinned', 'order', '-updated']

    def __str__(self):
        if self.title.strip():
            return self.title.strip()[:20]
        head = (self.body or '').strip().splitlines()[0] if self.body.strip() else '(空の付箋)'
        return head[:20]


def note_attachment_path(instance, filename):
    """付箋ごとにフォルダ分けして保存する（media/fusen/note/<id>/<file>）"""
    return f'fusen/note/{instance.note_id}/{filename}'


class Attachment(models.Model):
    """付箋に添付するファイル（スクリーンショット等の画像・PDF）"""
    note         = models.ForeignKey(Note, on_delete=models.CASCADE,
                                     related_name='attachments')
    file         = models.FileField(upload_to=note_attachment_path)
    name         = models.CharField(max_length=255)  # 元のファイル名
    content_type = models.CharField(max_length=100, blank=True)
    size         = models.PositiveIntegerField(default=0)
    order        = models.IntegerField(default=0)     # 付箋内の表示順
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


@receiver(post_delete, sender=Attachment)
def _delete_attachment_file(sender, instance, **kwargs):
    """レコード削除時に実ファイルもディスクから消す
    （付箋の削除でカスケードされた場合も含む）"""
    if instance.file:
        instance.file.delete(save=False)


class Task(models.Model):
    """タスク。期限とリマインド時刻を持ち、良いタイミングで思い出させる"""

    STATUS_TODO = 'todo'
    STATUS_DOING = 'doing'
    STATUS_DONE = 'done'
    STATUS_CHOICES = [
        (STATUS_TODO,  '未着手'),
        (STATUS_DOING, '進行中'),
        (STATUS_DONE,  '完了'),
    ]

    # 優先度（数値が大きいほど高い。並び替え・色分けに使う）
    PRIORITY_CHOICES = [
        (0, '低'),
        (1, '中'),
        (2, '高'),
    ]

    user      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name='tasks')
    title     = models.CharField(max_length=200)
    detail    = models.TextField(blank=True)
    tone      = models.CharField(max_length=10, choices=TONE_CHOICES, default='blue')
    status    = models.CharField(max_length=8, choices=STATUS_CHOICES, default=STATUS_TODO)
    priority  = models.IntegerField(choices=PRIORITY_CHOICES, default=1)

    due_at    = models.DateTimeField(null=True, blank=True)   # 期限（日付＋時刻）
    all_day   = models.BooleanField(default=False)            # 終日（時間軸に載せず終日帯へ）
    remind_at = models.DateTimeField(null=True, blank=True)   # 思い出すタイミング
    reminded  = models.BooleanField(default=False)            # リマインド済みフラグ

    done_at   = models.DateTimeField(null=True, blank=True)
    created   = models.DateTimeField(auto_now_add=True)
    updated   = models.DateTimeField(auto_now=True)

    class Meta:
        # 完了は後ろ、未完了は優先度高い順 → 期限が近い順
        ordering = ['done_at', '-priority', 'due_at', 'created']

    def __str__(self):
        return f'[{self.get_status_display()}] {self.title}'

    # ── 派生プロパティ（テンプレート/APIで使う） ──
    @property
    def is_done(self):
        return self.status == self.STATUS_DONE

    @property
    def is_overdue(self):
        return bool(self.due_at and not self.is_done and self.due_at < timezone.now())

    @property
    def is_due_soon(self):
        """24時間以内に期限が来る未完了タスク"""
        if not self.due_at or self.is_done:
            return False
        delta = self.due_at - timezone.now()
        return timezone.timedelta(0) <= delta <= timezone.timedelta(hours=24)

    @property
    def should_remind(self):
        """リマインド時刻を過ぎていて、まだ思い出していない未完了タスク"""
        return bool(
            self.remind_at and not self.reminded and not self.is_done
            and self.remind_at <= timezone.now()
        )
