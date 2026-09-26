from django.db import models


class MailMark(models.Model):
    """このサイト独自のマーク（★重要 など）。Gmail側には反映しない"""
    name       = models.CharField('名前', max_length=30)
    symbol     = models.CharField('記号', max_length=4, default='★')
    color      = models.CharField('色', max_length=20, default='yellow')
    sort_order = models.IntegerField('並び順', default=0)

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'{self.symbol} {self.name}'


class MailMarkAssign(models.Model):
    """メール（GmailのメッセージID）へのマーク付け"""
    mail_id    = models.CharField(max_length=64, db_index=True)
    mark       = models.ForeignKey(MailMark, on_delete=models.CASCADE, related_name='assigns')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['mail_id', 'mark'], name='uniq_mail_mark'),
        ]
