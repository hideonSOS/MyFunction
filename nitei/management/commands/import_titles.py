"""
titles.js の TITLES データを DB に一括インポートするコマンド。
usage: python manage.py import_titles
"""
from datetime import date
from django.core.management.base import BaseCommand
from nitei.models import Title

TITLES_DATA = [
    {"id": 1,  "date_from": "2026/4/3",   "date_to": "2026/4/8",   "venue": "都市", "title": "GⅠ太閤賞競走開設70周年記念"},
    {"id": 2,  "date_from": "2026/4/16",  "date_to": "2026/4/20",  "venue": "箕面", "title": "報知杯争奪第44回全国地区選抜戦"},
    {"id": 3,  "date_from": "2026/4/23",  "date_to": "2026/4/29",  "venue": "都市", "title": "スポニチ杯争奪第60回なにわ賞"},
    {"id": 4,  "date_from": "2026/5/3",   "date_to": "2026/5/8",   "venue": "箕面", "title": "オール大阪2026ラピートカップ"},
    {"id": 5,  "date_from": "2026/5/11",  "date_to": "2026/5/14",  "venue": "都市", "title": "寝屋川市制75周年記念競走"},
    {"id": 6,  "date_from": "2026/5/23",  "date_to": "2026/5/27",  "venue": "都市", "title": "アクアコンシェルジュカップ"},
    {"id": 7,  "date_from": "2026/5/30",  "date_to": "2026/6/3",   "venue": "都市", "title": "守口市制80周年記念競走"},
    {"id": 8,  "date_from": "2026/6/14",  "date_to": "2026/6/17",  "venue": "箕面", "title": "日本モータボート選手会長杯争奪2026ダイスポジャンピーカップ"},
    {"id": 9,  "date_from": "2026/6/24",  "date_to": "2026/6/29",  "venue": "都市", "title": "ヴィーナスシリーズ第7戦／大阪スポーツ賞第37回アクアクイーンカップ"},
    {"id": 10, "date_from": "2026/7/3",   "date_to": "2026/7/8",   "venue": "箕面", "title": "日刊スポーツ盾争奪ニッカン・コム杯 第60回しぶき杯競走"},
    {"id": 11, "date_from": "2026/7/15",  "date_to": "2026/7/21",  "venue": "都市", "title": "サンケイスポーツ旗争奪第69回GSS競走"},
    {"id": 12, "date_from": "2026/7/24",  "date_to": "2026/7/27",  "venue": "都市", "title": "豊中市制90周年記念競走"},
    {"id": 13, "date_from": "2026/8/4",   "date_to": "2026/8/9",   "venue": "都市", "title": "にっぽん未来プロジェクト競走 in 住之江"},
    {"id": 14, "date_from": "2026/8/13",  "date_to": "2026/8/18",  "venue": "箕面", "title": "大阪ダービー 第43回摂河泉競走"},
    {"id": 15, "date_from": "2026/9/1",   "date_to": "2026/9/6",   "venue": "都市", "title": "日刊スポーツ杯争奪 第30回ブルースターカップ（ニッカン・コム杯）"},
    {"id": 16, "date_from": "2026/9/11",  "date_to": "2026/9/16",  "venue": "都市", "title": "報知新聞社賞第62回ダイナミック敢闘旗"},
    {"id": 17, "date_from": "2026/9/18",  "date_to": "2026/9/23",  "venue": "箕面", "title": "サンケイスポーツ旗争奪第55回飛龍賞競走"},
    {"id": 18, "date_from": "2026/10/1",  "date_to": "2026/10/6",  "venue": "都市", "title": "2026東京・大阪・福岡三都市対抗戦"},
    {"id": 19, "date_from": "2026/10/10", "date_to": "2026/10/15", "venue": "箕面", "title": "にっぽん未来プロジェクト競走ｉｎ住之江"},
    {"id": 20, "date_from": "2026/10/19", "date_to": "2026/10/24", "venue": "箕面", "title": "GⅢ2026モーターボートレディスカップ"},
    {"id": 21, "date_from": "2026/11/5",  "date_to": "2026/11/10", "venue": "箕面", "title": "GⅠ第54回高松宮記念特別競走"},
    {"id": 22, "date_from": "2026/11/21", "date_to": "2026/11/26", "venue": "都市", "title": "サンテレビ杯争奪 ボートの時間！ご視聴ありがとう競走"},
    {"id": 23, "date_from": "2026/12/1",  "date_to": "2026/12/5",  "venue": "都市", "title": "BTSりんくう開設14周年記念競走"},
    {"id": 24, "date_from": "2026/12/12", "date_to": "2026/12/16", "venue": "箕面", "title": "スポニチ杯争奪第60回住之江選手権競走"},
    {"id": 25, "date_from": "2026/12/26", "date_to": "2026/12/31", "venue": "都市", "title": "PGⅠ第15回クイーンズクライマックス"},
    {"id": 26, "date_from": "2027/1/2",   "date_to": "2027/1/7",   "venue": "都市", "title": "第65回全大阪王将戦"},
    {"id": 27, "date_from": "2027/1/10",  "date_to": "2027/1/15",  "venue": "箕面", "title": "GⅢ第37回アサヒビールカップ"},
    {"id": 28, "date_from": "2027/1/25",  "date_to": "2027/1/30",  "venue": "箕面", "title": "第58回住之江選手権競走（マスターズリーグ10戦）"},
    {"id": 29, "date_from": "2027/2/2",   "date_to": "2027/2/7",   "venue": "都市", "title": "BTS大和ごせ開設13周年記念 トランスワードトロフィー2027"},
    {"id": 30, "date_from": "2027/2/10",  "date_to": "2027/2/15",  "venue": "都市", "title": "デイリースポーツ旗争奪 第68回ホワイトベア競走"},
    {"id": 31, "date_from": "2027/2/20",  "date_to": "2027/2/23",  "venue": "箕面", "title": "第19回森下仁丹杯争奪戦"},
    {"id": 32, "date_from": "2027/2/26",  "date_to": "2027/3/3",   "venue": "箕面", "title": "ボートピア梅田開設20周年記念 デイリースポーツ杯争奪 2027サザンカップ"},
    {"id": 33, "date_from": "2027/3/6",   "date_to": "2027/3/11",  "venue": "都市", "title": "第9回auじぶん銀行賞"},
    {"id": 34, "date_from": "2027/3/18",  "date_to": "2027/3/22",  "venue": "都市", "title": "一般競走"},
    {"id": 35, "date_from": "2027/3/24",  "date_to": "2027/3/29",  "venue": "箕面", "title": "スカパー！・JLC杯競走 （ルーキーシリーズ第6戦）"},
]


def parse_date(s):
    y, m, d = s.split('/')
    return date(int(y), int(m), int(d))


class Command(BaseCommand):
    help = 'titles.js のデータを Title テーブルにインポートする'

    def handle(self, *args, **kwargs):
        created = updated = 0
        for row in TITLES_DATA:
            obj, is_new = Title.objects.update_or_create(
                id=row['id'],
                defaults={
                    'date_from': parse_date(row['date_from']),
                    'date_to':   parse_date(row['date_to']),
                    'venue':     row['venue'],
                    'title':     row['title'],
                    'order':     row['id'],
                }
            )
            if is_new:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(f'完了: {created}件追加 / {updated}件更新'))
