from django.db import models


class Title(models.Model):
    """開催タイトルマスター"""
    date_from = models.DateField()
    date_to = models.DateField()
    venue = models.CharField(max_length=50)  # 都市 / 箕面
    title = models.CharField(max_length=300)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['date_from']

    def __str__(self):
        return f"{self.date_from}〜{self.date_to} [{self.venue}] {self.title}"


class WorkEntry(models.Model):
    """勤務記録（1セル = 1レコード）"""
    STATUS_CHOICES = [
        ('公開FM', '公開FM'),
        ('有給',   '有給'),
        ('公休',   '公休'),
        ('本社',   '本社'),
        ('公出勤', '公出勤'),
        ('',       '未入力'),
    ]
    sheet_index   = models.IntegerField()
    section_index = models.IntegerField()
    day_index     = models.IntegerField()
    status        = models.CharField(max_length=20, blank=True, choices=STATUS_CHOICES)

    class Meta:
        unique_together = ('sheet_index', 'section_index', 'day_index')

    def __str__(self):
        return f"w_{self.sheet_index}_{self.section_index}_{self.day_index}={self.status}"
