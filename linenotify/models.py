from django.db import models


class LineTarget(models.Model):
    """LINEの送信先（グループ・トークルーム・ユーザー）。
    Webhook でボットがグループに招待されると自動登録される。手動登録も可"""
    KIND_CHOICES = [
        ('group', 'グループ'),
        ('room',  'トークルーム'),
        ('user',  'ユーザー'),
    ]
    name      = models.CharField(max_length=100)             # 表示名（編集可）
    target_id = models.CharField(max_length=64, unique=True) # groupId / roomId / userId
    kind      = models.CharField(max_length=8, choices=KIND_CHOICES, default='group')
    created   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created']

    def __str__(self):
        return f'{self.name} ({self.get_kind_display()})'


class LineNotification(models.Model):
    """LINE予約通知。指定の日時になったらメッセージをLINEへ送る。
    target 未設定ならブロードキャスト（友だち全員）、設定済みならその宛先へ"""
    date    = models.DateField()                       # 送信日
    time    = models.TimeField()                       # 送信時刻
    message = models.TextField(max_length=1000)        # 本文
    target  = models.ForeignKey(LineTarget, null=True, blank=True,
                                on_delete=models.SET_NULL,
                                related_name='notifications')

    sent    = models.BooleanField(default=False)       # 送信済みフラグ
    sent_at = models.DateTimeField(null=True, blank=True)
    error   = models.CharField(max_length=200, blank=True)  # 直近の送信エラー

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sent', 'date', 'time']

    def __str__(self):
        state = '済' if self.sent else '予約'
        return f'[{state}] {self.date} {self.time} {self.message[:20]}'
