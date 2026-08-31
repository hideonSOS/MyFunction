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

        # 送信済みの残骸を掃除（送信成功時は即削除されるが、旧データや
        # 削除失敗分への保険。送信直後の並行プロセス分を消さないよう10分の猶予）
        LineNotification.objects.filter(
            sent=True, sent_at__lt=timezone.now() - timezone.timedelta(minutes=10)
        ).delete()

        due = []
        for n in LineNotification.objects.filter(sent=False).select_related('target'):
            when = timezone.make_aware(
                datetime.combine(n.date, n.time), timezone.get_current_timezone())
            if when <= now:
                due.append(n)

        if not due:
            return

        for n in due:
            # 二重送信防止: 送信前に原子的に「送信済み」へ更新してクレームする。
            # cron の実行が重なっても、更新できた1プロセスだけが送信する
            claimed = LineNotification.objects.filter(id=n.id, sent=False).update(
                sent=True, sent_at=timezone.now(), error='')
            if not claimed:
                continue   # 別プロセスが処理済み

            ok, err = line_api.send_to(n.target, n.message)
            if ok:
                # 送信成功した予約は自動削除（手動削除の手間をなくす）
                LineNotification.objects.filter(id=n.id).delete()
                self.stdout.write(f'[{now:%Y-%m-%d %H:%M}] sent+removed id={n.id} {n.message[:30]}')
            else:
                # 失敗したら未送信へ戻して次回リトライ（エラーを記録）
                LineNotification.objects.filter(id=n.id).update(
                    sent=False, sent_at=None, error=err)
                self.stderr.write(f'[{now:%Y-%m-%d %H:%M}] FAILED id={n.id} {err}')
