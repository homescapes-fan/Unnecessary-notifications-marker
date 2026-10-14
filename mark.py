"""お知らせ一覧で、未読かつタイトルにキーワードを含むものを既読にする。

タスク スケジューラから 30 分おきに実行される。

    python mark.py             通常の実行（既読を付ける）
    python mark.py --dry-run   既読にせず、対象を表示するだけ
"""
import sys
import traceback
import unicodedata
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# このファイルがあるフォルダを基準にする。どこから実行しても同じファイルを使うため
BASE = Path(__file__).parent
# ログイン状態は、学部生ページ通知ツールのものを読むだけで共用する（こちらからは上書きしない）
AUTH = BASE.parent / "Undergraduate-student-page-notifier" / "auth.json"
KEYWORDS = BASE / "keywords.txt"
MARKED_LOG = BASE / "marked.log"
ERROR_LOG = BASE / "error.log"

URL = "https://sp.ritsumei.ac.jp/studentportal/s/information-home"
ROWS = "tr[data-row-number]"


class ReadError(Exception):
    """ページが想定どおりに読み取れなかったとき"""


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize(text):
    """全角・半角の違いをそろえる（「ＩＥＬＴＳ」と「IELTS」を同じに扱うため）"""
    return unicodedata.normalize("NFKC", text)


def load_keywords():
    """keywords.txt を 1 行 1 語で読む。空行と # で始まる行は無視する"""
    if not KEYWORDS.exists():
        raise ReadError("keywords.txt がありません。keywords.example.txt をコピーして作ってください")
    words = []
    for line in KEYWORDS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            words.append(normalize(line))
    return words


def read_list(page):
    """一覧を全件表示して、[{"title", "url", "unread"}] を返す"""
    rows = page.locator(ROWS)
    # 一覧が表示されるまで待つ
    rows.first.wait_for(timeout=30000)

    # 最初は 10 件だけ。「すべて表示」を押すと全件が読み込まれる
    show_all = page.get_by_role("button", name="すべて表示")
    if show_all.count() > 0:
        before = rows.count()
        show_all.click()
        for _ in range(60):
            if rows.count() > before:
                break
            page.wait_for_timeout(500)
        # 件数が増え終わるまで待つ（読み込み途中で数えないため）
        count = rows.count()
        while True:
            page.wait_for_timeout(1000)
            if rows.count() == count:
                break
            count = rows.count()

    # 上から一件ずつタイトル・未読/既読状態を取得する
    items = []
    for i in range(rows.count()):
        row = rows.nth(i)
        link = row.locator('th[data-label="タイトル"] a')
        status = row.locator('td[data-label="既読/未読"]').get_attribute("data-cell-value") or ""
        if "未読" not in status and "既読" not in status:
            raise ReadError(f"{i + 1} 行目の既読/未読が読めません: {status!r}")
        items.append({
            "title": link.get_attribute("title") or link.inner_text(),
            "url": link.get_attribute("href"),
            "unread": "未読" in status,
        })
    return items


def mark_read(context, page, item):
    """タイトルをクリックして別ウィンドウで開き、読み込みが終わったら閉じる（これで既読になる）"""
    link = page.locator(f'th[data-label="タイトル"] a[href="{item["url"]}"]')
    # クリックの前に「新しいページが開くのを待つ」構えを作る（後からだと見逃すことがある）
    with context.expect_page() as new_page_info:
        link.click()
    new_page = new_page_info.value
    new_page.wait_for_load_state("load")
    # 既読の記録は読み込みの後に裏の通信で行われるので、通信が落ち着くまで待つ
    try:
        new_page.wait_for_load_state("networkidle", timeout=15000)
    except PlaywrightTimeoutError:
        pass
    new_page.close()


def log_marked(lines):
    with MARKED_LOG.open("a", encoding="utf-8") as f:
        for line in lines:
            f.write(f"{now()}\t{line}\n")


def run(dry_run):
    keywords = load_keywords()

    with sync_playwright() as p:
        # ブラウザを開く（定期実行なので画面は出さない）
        browser = p.chromium.launch(headless=True, channel="chrome")

        # auth.jsonを渡す
        context = browser.new_context(storage_state=AUTH)

        # お知らせぺーじのURLを開く
        page = context.new_page()
        page.goto(URL)
        if not page.url.startswith("https://sp.ritsumei.ac.jp/"):
            raise ReadError(f"ログインが切れています（{page.url} に移動しました）")

        items = read_list(page)
        targets = [
            item for item in items
            if item["unread"] and any(word in normalize(item["title"]) for word in keywords)
        ]

        unread = sum(item["unread"] for item in items)
        print(f"{len(items)} 件中、未読 {unread} 件、既読にする対象 {len(targets)} 件")
        for item in targets:
            print(f"  {item['title']}")

        if dry_run or not targets:
            browser.close()
            return

        for item in targets:
            mark_read(context, page, item)

        # 本当に既読になったかを、一覧を読み直して確かめる
        page.reload()
        after = {item["url"]: item for item in read_list(page)}
        done = [item for item in targets if item["url"] in after and not after[item["url"]]["unread"]]
        failed = [item for item in targets if item not in done]

        log_marked([f"既読にした\t{item['title']}" for item in done])
        print(f"既読にした：{len(done)} 件")
        if failed:
            raise ReadError("既読にならなかったもの：" + " / ".join(item["title"] for item in failed))

        browser.close()


def main():
    dry_run = "--dry-run" in sys.argv
    # 絵文字入りのタイトルを表示してもエラーにならないようにする（pythonw では stdout が None）
    if sys.stdout:
        sys.stdout.reconfigure(errors="replace")
    try:
        run(dry_run)
    except Exception:
        # pythonw で動くと画面に何も出ないので、原因をファイルに残す
        with ERROR_LOG.open("a", encoding="utf-8") as f:
            f.write(f"===== {now()}\n{traceback.format_exc()}\n")
        raise


if __name__ == "__main__":
    main()
