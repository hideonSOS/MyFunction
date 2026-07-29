from django.conf import settings
from django.db import models
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
    body     = models.TextField(blank=True)
    tone     = models.CharField(max_length=10, choices=TONE_CHOICES, default='yellow')
    pinned   = models.BooleanField(default=False)
    archived = models.BooleanField(default=False)
    date     = models.DateField(null=True, blank=True)  # カレンダー上の配置日（未設定=未分類）
    order    = models.IntegerField(default=0)          # ボード内の並び順
    created  = models.DateTimeField(auto_now_add=True)
    updated  = models.DateTimeField(auto_now=True)

    class Meta:
        # ピン留め優先 → 手動並び順 → 新しい順
        ordering = ['-pinned', 'order', '-updated']

    def __str__(self):
        head = (self.body or '').strip().splitlines()[0] if self.body.strip() else '(空の付箋)'
        return head[:20]


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

    due_at    = models.DateTimeField(null=True, blank=True)   # 期限
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
