# ConoHaサーバー接続 反省点まとめ

## 1. Claude Code の認証（OAuth vs APIキー）

### 問題
- サーバー側でClaude Codeを初期設定する際、OAuthフローでブラウザが開けなかった
- URLをターミナルからコピーすると改行が混入し「無効なOAuth要求」エラーになった

### 教訓
- **サーバー環境ではAPIキー認証を最初から使う**
- `export ANTHROPIC_API_KEY="sk-ant-..."` を `.bashrc` に設定するのが最もシンプル
- OAuth認証はブラウザのある環境（ローカルPC）向け

---

## 2. Tera Term と Claude Code の相性問題

### 問題
- Claude Code の TUI（対話UI）がTera Termで正しく描画されない
- `q` が大量に表示される（ボックス描画文字の文字化け）
- 操作中に `Interrupted · What should Claude do instead?` が頻発して作業が止まった

### 原因
- Tera Termのデフォルト端末種別がxterm非対応
- 日本語入力がClaudeの入力を誤検知してESCシーケンスを送信していた可能性

### 教訓
- **サーバーでClaude Codeを使う場合はWindows Terminalを使う**
- Tera Termを使う場合は `Setup → Terminal → Terminal ID` を `xterm-256color` に変更
- 長い自動作業は対話モードを避け `-p` フラグで一括指示する：
  ```bash
  claude --dangerously-skip-permissions -p "作業内容"
  ```

---

## 3. SSH接続（Windows Terminal から）

### 問題
- 今までTera Termのみでサーバー接続していたため、Windows Terminalからの接続方法を知らなかった
- 鍵ファイルが `.ppk`（PuTTY形式）のためOpenSSHで使えなかった

### 解決手順
1. PuTTYgenで `.ppk` → `.pem`（OpenSSH形式）に変換
   - PuTTYgen → Load → `Conversions → Export OpenSSH key`
2. Windows Terminalから接続：
   ```bash
   ssh -i "C:\Users\matsuyama\.ssh\MyFunctionKey.pem" root@133.88.121.139
   ```

### 教訓
- **Windows TerminalはClaude Codeとの相性が良くTera Termの問題を回避できる**
- 鍵ファイルは `.pem` 形式（OpenSSH形式）で管理しておく
- 今後の鍵作成時は最初からOpenSSH形式で作成する

---

## 4. 今後のサーバー作業フロー（推奨）

```
1. Windows Terminal で ssh -i ~/.ssh/MyFunctionKey.pem root@133.88.121.139
2. サーバーで ANTHROPIC_API_KEY を設定済みの状態で claude 起動
3. 必要に応じて tmux でセッション管理
```
