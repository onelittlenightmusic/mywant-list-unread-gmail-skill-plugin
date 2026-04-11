#!/usr/bin/env python3
"""
list-unread-gmail: GmailのImportantラベルにある未読メールを番号付きで一覧表示する。
結果を /tmp/gmail_unread_list.json に保存し、mark-read から参照できるようにする。
"""
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

CDP_URL = "http://127.0.0.1:9222"
CACHE_FILE = "/tmp/gmail_unread_list.json"

GMAIL_IMPORTANT_URL = "https://mail.google.com/mail/u/0/#imp"


def fetch_unread_important(page) -> list[dict]:
    page.goto(GMAIL_IMPORTANT_URL, wait_until="domcontentloaded", timeout=15000)

    # ページが安定するまで少し待つ
    try:
        page.wait_for_selector("div[role='main']", timeout=10000)
    except PlaywrightTimeout:
        print("ERROR: Gmailの読み込みがタイムアウトしました。ログイン状態を確認してください。", file=sys.stderr)
        sys.exit(1)

    emails = []
    # 未読行: .zE クラス（Gmail の未読スレッド）を持つ tr を取得
    rows = page.query_selector_all("tr.zE")
    if not rows:
        # フォールバック: aria-label に "未読" を含む行
        rows = page.query_selector_all("tr[aria-label]")
        rows = [r for r in rows if "未読" in (r.get_attribute("aria-label") or "")]

    for i, row in enumerate(rows, start=1):
        # 送信者
        sender_el = row.query_selector("span.yX.xY")
        sender = sender_el.inner_text().strip() if sender_el else "(不明)"

        # 件名
        subject_el = row.query_selector("span.bqe") or row.query_selector("span[data-thread-id]")
        if not subject_el:
            subject_el = row.query_selector("span.bog")
        subject = subject_el.inner_text().strip() if subject_el else "(件名なし)"

        # 日時
        date_el = row.query_selector("span.xW.xY") or row.query_selector("td.xW")
        date = date_el.inner_text().strip() if date_el else ""

        # スレッドID（既読操作時に使用）
        thread_id = row.get_attribute("data-thread-id") or ""

        emails.append({
            "no": i,
            "sender": sender,
            "subject": subject,
            "date": date,
            "thread_id": thread_id,
        })

    return emails


def main():
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL)
        except Exception as e:
            print(f"ERROR: ブラウザに接続できません ({CDP_URL}): {e}", file=sys.stderr)
            sys.exit(1)

        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.pages[0] if context.pages else context.new_page()

        emails = fetch_unread_important(page)

    if not emails:
        print("未読の重要メールはありません。")
        Path(CACHE_FILE).write_text(json.dumps([], ensure_ascii=False))
        return

    # キャッシュ保存
    Path(CACHE_FILE).write_text(json.dumps(emails, ensure_ascii=False, indent=2))

    print(f"未読の重要メール ({len(emails)} 件):\n")
    for e in emails:
        print(f"[{e['no']}] {e['subject']}")
        print(f"     差出人: {e['sender']}  {e['date']}")
        print()


if __name__ == "__main__":
    main()
