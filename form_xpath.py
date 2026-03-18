"""
form_xpath.py  –  フォーム別 XPath 定数
ringi_inspect.py の調査結果から確定したIDベースXPathを定義する。
IDはフォーム定義に紐づくため、インスタンスが変わっても不変。
"""

# ============================================================
# 共通（ログイン・ナビゲーション）
# ============================================================
COMMON = {
    'sel_btn':        '//input[@class="jco-sel-btn"]',
    'tree1':          "(//ins[@class='jstree-icon'])[11]",
    'tree2':          "(//ins[@class='jstree-icon'])[14]",
    'user':           "//select[@name='uid']/option[@value='23']",
    'pw':             "//input[@class='co-width-100p']",
    'login':          "//a[@id='login-btn']",
    'status_select':  "(//select)[4]",
    'copy_btn':       "//input[@value='複写して作成']",
    'draft_btn':      "//input[@value='下書き保存'] | //button[contains(text(),'下書き')]",
    'iframe':         "//iframe[contains(@src, 'appsuite.cgi?cmd=cdbbrowsedetailframe')]",
    'subject':        '//input[@class="jco-input-subject co-width-long"]',
}

# ============================================================
# 契約連絡表（ringi_inspect.py 調査結果 2026-03-18確定）
# ============================================================
KEIYAKU = {
    # --- input ---
    'keiyaku_saki':   '//*[@id="jcdb-part-item19cfc5e263cde64"]',  # [1] 契約先名
    'keiyaku_tanto':  '//*[@id="jcdb-part-item19cfc5e263d8865"]',  # [2] 契約担当
    'genba_tanto':    '//*[@id="jcdb-part-item19cfc5e263e7670"]',  # [3] 現場担当
    'tel':            '//*[@id="jcdb-part-item19cfc5e2641e99b"]',  # [4] TEL
    'shozaichi':      '//*[@id="jcdb-part-item19cfc5e2642efef"]',  # [5] 所在地
    'gyomu_bi':       '//*[@id="jcdb-part-item19cfc5e2643cbda"]',  # [6] 業務日
    'inp7':           '//*[@id="jcdb-part-item19cfc5e26444b33"]',  # [7] 不明（空）
    'zeibiki':        '//*[@id="jcdb-part-item19cfc5e26472e14"]',  # [8] 税抜き
    'inp9':           '//*[@id="jcdb-part-item19cfc5e2648509c"]',  # [9] 不明（空）
    'sochi_saki':     '//*[@id="jcdb-part-item19cfc5e264a75bb"]',  # [10] 送付先 社名
    'sochi_jusho':    '//*[@id="jcdb-part-item19cfc5e264b98b7"]',  # [11] 送付先 住所/宛先

    # --- textarea ---
    'gyomu_tai':      '//*[@id="jcdb-part-item19cfc5e263f6ee0"]',  # [T1] 業務対象
    'gyomu_naiyo':    '//*[@id="jcdb-part-item19cfc5e2644575d"]',  # [T2] 業務内容
    'zei_text':       '//*[@id="jcdb-part-item19cfc5e2647e74c"]',  # [T3] 消費税・総額
    'sonota':         '//*[@id="jcdb-part-item19cfc5e264bb737"]',  # [T4] その他
}

# ============================================================
# 外注費連絡表（ringi_inspect.py 調査結果 2026-03-18確定）
# ============================================================
GAICHUU = {
    # --- input ---
    'gaichuu_saki':   '//*[@id="jcdb-part-item19cfc60075de68d"]',  # [1]  外注先名
    'keiyaku_tanto':  '//*[@id="jcdb-part-item19cfc60075e4966"]',  # [2]  契約担当
    'gyomu_tanto':    '//*[@id="jcdb-part-item19cfc60075f800a"]',  # [3]  業務担当
    'tel':            '//*[@id="jcdb-part-item19cfc6007625f5a"]',  # [4]  TEL
    'shozaichi':      '//*[@id="jcdb-part-item19cfc600763dc27"]',  # [5]  所在地
    'gyomu_bi':       '//*[@id="jcdb-part-item19cfc600764582b"]',  # [6]  業務日
    'gyomu_naiyo':    '//*[@id="jcdb-part-item19cfc6007656dbf"]',  # [7]  業務内容（1行）
    'zeibiki':        '//*[@id="jcdb-part-item19cfc60076a167f"]',  # [8]  税抜き
    'shiharai_hoho':  '//*[@id="jcdb-part-item19cfc60076de456"]',  # [9]  支払方法
    'ginko_mei':      '//*[@id="jcdb-part-item19cfc60076fde2a"]',  # [10] 銀行名
    'shiten_mei':     '//*[@id="jcdb-part-item19cfc6007704ee2"]',  # [11] 支店名
    'koza_bango':     '//*[@id="jcdb-part-item19cfc6007715fd0"]',  # [12] 口座番号
    'koza_meigi':     '//*[@id="jcdb-part-item19cfc600772f581"]',  # [13] 口座名義

    # --- textarea ---
    'gyomu_tai':      '//*[@id="jcdb-part-item19cfc6007607283"]',  # [T1] 業務対象
    'tanto_jikan':    '//*[@id="jcdb-part-item19cfc600766ce8d"]',  # [T2] 担当時間
    'zei_text':       '//*[@id="jcdb-part-item19cfc60076b8daa"]',  # [T3] 消費税・総額
    'sonota':         '//*[@id="jcdb-part-item19cfc60077295e0"]',  # [T4] その他
}
