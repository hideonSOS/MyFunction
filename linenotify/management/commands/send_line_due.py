"""予約時刻を過ぎた未送信のLINE通知を送る。

本番サーバーの cron で毎分実行する想定:
    * * * * * cd /srv/MyFunction && ./venv/bin/python manage.py send_line_due >> logs/line_notify.log 2>&1
"""
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from linenotify.models import LineNotification
from linenotify import line_api


class Command(BaseCommand):
    help = '予約時刻を過ぎた未送信のLINE通知を送信する'

    def handle(self, *args, **options):
        now = timezone.localtime()
        due = []
        for n in LineNotification.objects.filter(sent=False).select_related('target'):
            when = timezone.make_aware(
                datetime.combine(n.date, n.time), timezone.get_current_timezone())
            if when <= now:
                due.append(n)

        if not due:
            return

        for n in due:
            ok, err = line_api.send_to(n.target, n.message)
            if ok:
                n.sent = True
                n.sent_at = timezone.now()
                n.error = ''
                self.stdout.write(f'[{now:%Y-%m-%d %H:%M}] sent id={n.id} {n.message[:30]}')
            else:
                n.error = err
                self.stderr.write(f'[{now:%Y-%m-%d %H:%M}] FAILED id={n.id} {err}')
            n.save()
