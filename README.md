# Unnecessary-notifications-marker
Ritsumeikan Student portal のお知らせに自動で既読を付けます。

[お知らせ一覧](https://sp.ritsumei.ac.jp/studentportal/s/information-home)のうち、**未読**で、タイトルに `keywords.txt` の言葉を 1 つでも含むものを既読にします。既読は、人が操作するときと同じく、タイトルをクリックして別ウィンドウで開き、読み込みが終わったら閉じることで付けています。

## 必要なもの
- Windows と Google Chrome（画面を出さずに PC の Chrome を使います）
- [Undergraduate-student-page-notifier](https://github.com/homescapes-fan/Undergraduate-student-page-notifier) が同じフォルダに並んで置かれ、`auth.json`（ログイン状態）が作られていること。このツールはそれを読むだけで、書き換えません

```
GitHub/
├── Undergraduate-student-page-notifier/auth.json
└── Unnecessary-notifications-marker/mark.py
```

## 準備
```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

## 使い方
```bash
python mark.py --dry-run   # 既読にせず、対象を表示するだけ
python mark.py             # 既読を付ける
```

既読にする言葉は `keywords.txt` に 1 行 1 語で書きます。`#` で始まる行と空行は無視され、全角・半角の違いは区別しません。

## 記録
- `marked.log`：既読にしたお知らせのタイトル
- `error.log`：失敗したときの原因（ログイン切れなど）

## 定期実行
タスク スケジューラで 30 分おき（毎時 15 分・45 分）に `pythonw.exe mark.py` を実行しています。通知ツールが auth.json を書き換える毎時 0 分・30 分とずらしています。
