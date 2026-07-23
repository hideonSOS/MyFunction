from django.db import models


PERSON_CHOICES = [
    ('a', '松山'),
    ('b', '竹田津'),
    ('c', '金山'),
    ('d', '三室'),
    ('e', '山田'),
    ('f', '芳松'),
    ('g', '表木'),
    ('h', '虎谷'),
    ('i', '栗原'),
    ('j', '小林'),
    ('k', 'S水'),
    ('l', 'I田'),
]

PERSONS = {k: v for k, v in PERSON_CHOICES}


# 配置図（1日単位）の既定レイアウト
LAYOUT_RACE_COUNT = 12
LAYOUT_DEFAULT_HEADERS = ['ホワイトボード', '映像', 'JLC', '音声', '', '']
LAYOUT_COL_COUNT = len(LAYOUT_DEFAULT_HEADERS)


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
    ROW_TYPE_CHOICES = [(0, '上番'), (1, '下番')]

    person        = models.CharField(max_length=1, choices=PERSON_CHOICES, default='a')
    sheet_index   = models.IntegerField()
    section_index = models.IntegerField()
    day_index     = models.IntegerField()
    row_type      = models.IntegerField(default=0, choices=ROW_TYPE_CHOICES)
    status        = models.CharField(max_length=20, blank=True)  # HH:MM 形式の時刻文字列

    class Meta:
        unique_together = ('person', 'sheet_index', 'section_index', 'day_index', 'row_type')

    def __str__(self):
        return f"{self.person}:w_{self.sheet_index}_{self.section_index}_{self.day_index}={self.status}"


class EventEntry(models.Model):
    """開催行 時間メモ（1セル = 1レコード）"""
    person        = models.CharField(max_length=1, choices=PERSON_CHOICES, default='a')
    sheet_index   = models.IntegerField()
    section_index = models.IntegerField()
    day_index     = models.IntegerField()
    time_text     = models.CharField(max_length=20, blank=True)

    class Meta:
        unique_together = ('person', 'sheet_index', 'section_index', 'day_index')

    def __str__(self):
        return f"{self.person}:e_{self.sheet_index}_{self.section_index}_{self.day_index}={self.time_text}"


# ── 配置図（1日単位） ──────────────────────────────────

class LayoutDay(models.Model):
    """1日分の配置図"""
    date    = models.DateField(unique=True)
    headers = models.JSONField(default=list)  # ポジション列名（6列）

    class Meta:
        ordering = ['date']

    def __str__(self):
        return f"配置図 {self.date}"


class LayoutRace(models.Model):
    """レース行の時刻（発売開始 / 締め切り）"""
    day        = models.ForeignKey(LayoutDay, related_name='races', on_delete=models.CASCADE)
    race       = models.PositiveSmallIntegerField()          # 1〜12
    start_time = models.CharField(max_length=5, blank=True)  # 発売開始 HH:MM
    close_time = models.CharField(max_length=5, blank=True)  # 締め切り HH:MM
    highlight  = models.BooleanField(default=False)          # レース番号の着色

    class Meta:
        unique_together = ('day', 'race')
        ordering = ['race']

    def __str__(self):
        return f"{self.day.date} {self.race}R {self.start_time}〜{self.close_time}"


class LayoutCell(models.Model):
    """配置セル（1セル = 1レコード、自由テキスト）"""
    day  = models.ForeignKey(LayoutDay, related_name='cells', on_delete=models.CASCADE)
    race = models.PositiveSmallIntegerField()  # 1〜12
    col  = models.PositiveSmallIntegerField()  # 0〜5
    text = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ('day', 'race', 'col')
        ordering = ['race', 'col']

    def __str__(self):
        return f"{self.day.date} {self.race}R col{self.col}={self.text}"

