import json
import os
import datetime
import requests
import feedparser
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import time
import re

# ログファイルとログレベルの設定
LOG_FILE = "rss_reader.log"
if os.path.exists(LOG_FILE): # 既存のログファイルがあれば削除
    os.remove(LOG_FILE)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)


# --- 設定 ---
BOOKMARKS_PATH = os.path.expanduser(
    r'C:\Users\<User name>\AppData\Local\Google\Chrome\User Data\Default\Bookmarks'  # You need to configure it before execution
)
TARGET_FOLDER_NAME = "web-manga" # You need to configure it before execution
OUTPUT_FILE = "recent_feeds.txt"

# Atomを使用しているRSSフィードの名前空間定義（gigaタグを使っているRSSに合わせて更新してください）
NAMESPACES_ATOM = {
    'atom': 'http://www.w3.org/2005/Atom',
    'giga': 'https://gigaviewer.com'  # 実際のRSSのnamespace URIに合わせて変更
}

# RSSを使用しているRSSフィードの名前空間定義（gigaタグを使っているRSSに合わせて更新してください）
NAMESPACES_RSS = {
    'giga': 'https://gigaviewer.com'  # 実際のRSSのnamespace URIに合わせて変更
}

# HTTPリクエストヘッダー定義
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    )
}

# --- 関数定義 ---

def find_manga_folder(bookmark_data, folder_name):
    def search(node):
        if node.get("type") == "folder" and node.get("name") == folder_name:
            return node.get("children", [])
        for child in node.get("children", []):
            result = search(child)
            if result:
                return result
        return None
    return search(bookmark_data["roots"]["bookmark_bar"])

def find_rss_url(name, site_url):
    try:
        res = requests.get(site_url, headers=HEADERS, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")

        # 1. <link> タグ: rel="alternate" + type="application/rss+xml"
        for link in soup.find_all("link", rel="alternate"):
            if link.get("type") in ["application/rss+xml", "application/atom+xml"]:
                href = link.get("href")
                if href:
                    return urljoin(site_url, href)

        # 2. <a> タグで href に "rss" を含むものを調べる
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            text = a.get_text(strip=True).lower()
            
            img = a.find("img")
            img_alt = img.get("alt", "").lower() if img else ""
            img_src = img.get("src", "").lower() if img else ""

            # RSSらしさの判定
            if (
                "rss" in href or                     # URLにrssが含まれる
                "rss" in text or                     # aタグのテキストにrssが含まれる
                "rss_feed" in text or                # aタグのテキストにrss_feedが含まれる
                "rss" in img_alt or                  # マテリアルアイコンのalt属性にrss
                "rss.svg" in img_src                 # マテリアルアイコンのsrcにrss.svg
            ):
                return urljoin(site_url, a["href"])

        # RSSが見つからなかった場合
        logging.error(f"RSSフィードを検出することが出来ませんでした: {name} : {site_url}")
        return None

    except Exception as e:
        logging.exception(f"[!] RSS URL取得エラー: {name} : {site_url} ({e})")
        return None

def get_updated_date(name, feed_url):
    try:
        feed = feedparser.parse(feed_url)
        updated_date = feed.feed.get('updated_parsed') or feed.feed.get('published_parsed') or None
        if updated_date == None:
            updated_date_of_latest_item = feed.entries[0].get('updated_parsed') or feed.entries[0].get('published_parsed')
            if updated_date_of_latest_item:
                return datetime.fromtimestamp(time.mktime(updated_date_of_latest_item))
            logging.warning(f"RSSフィード内のエントリーを検出しましたが、更新日時の取得に失敗しましsた: {name} : {feed_url}")
            return None
        else:
            return datetime.fromtimestamp(time.mktime(updated_date))
    except Exception as e:
        logging.exception(f"[!] フィード解析失敗: {name} : {feed_url} ({e})")
        return None

# RSSフィードが<giga:freeTermStartDate>タグを含む場合、<giga:freeTermStartDate>の日時を取得する
# サンプル：https://comic-days.com/atom/series/13933686331730851805
def get_free_term_start_date(feed_url):
    list_regexp_rss = [r"/rss/", r"/rss$"]
    list_regexp_atom = [r"/atom/", r"/atom$"]
    namespace = None
    entries = None
    format_date_time = None
    try:
        res = requests.get(feed_url, headers=HEADERS, timeout=10)
        res.raise_for_status()
        root = ET.fromstring(res.content)

        if any(re.search(pattern, feed_url) for pattern in list_regexp_rss):
            namespace = NAMESPACES_RSS
            entries = root.find('channel').findall('item')
            format_date_time = '%a, %d %b %Y %H:%M:%S %z'
        elif any(re.search(pattern, feed_url) for pattern in list_regexp_atom):
            namespace = NAMESPACES_ATOM
            entries = root.findall('atom:entry', NAMESPACES_ATOM)
            format_date_time = "%Y-%m-%dT%H:%M:%SZ"

        free_term_start_date = None # (freeTermStartDate, 当該エントリーの公開日) のタプル
        for entry in entries:
            # <giga:freeTermStartDate> を取得
            free_elem = entry.find("giga:freeTermStartDate", namespace)
            if free_elem is not None:
                try:
                    free_date = datetime.strptime(free_elem.text, format_date_time)
                    # ループ1回目の処理：max_date がまだ未定義であるため値を代入する
                    # ループ2回目以降の処理：すでに記録してある free_term_start_date よりも現在の free_date の方が新しければ、 free_term_start_date を更新する
                    if (free_term_start_date is None) or (free_date > free_term_start_date):
                        free_term_start_date = free_date
                except Exception as e:
                    continue  # 無効な日付はスキップ

        if free_term_start_date:
            return free_term_start_date
    except Exception as e:
        return None

def is_older_than_7_days(name, feed_url):
    updated_date = None
    free_term_date = None

    # 各日付を取得
    updated_date = get_updated_date(name, feed_url)
    free_term_date = get_free_term_start_date(feed_url)
    logging.debug(f"更新日:無料公開日 = {updated_date}:{free_term_date}")

    # 比較用の最新日付
    valid_dates = [d for d in [updated_date, free_term_date] if d is not None]
    if not valid_dates:
        logging.warning(f"[!] {name} の日付が取得できませんでした")
        return True, None

    latest_date = max(valid_dates)
    logging.debug(f"最終更新日 = {latest_date}")
    delta = datetime.now(latest_date.tzinfo) - latest_date
    logging.debug(f"直近7日以内の更新である = {delta.days <= 7, latest_date.strftime("%Y-%m-%d")}")
    return delta.days <= 7, latest_date.strftime("%Y-%m-%d")

# --- メイン処理 ---

def main():
    # 1. ブックマークファイルの読み込み
    with open(BOOKMARKS_PATH, "r", encoding="utf-8") as f:
        bookmark_data = json.load(f)

    # 2. 「漫画」フォルダのブックマークを取得
    manga_sites = find_manga_folder(bookmark_data, TARGET_FOLDER_NAME)
    if not manga_sites:
        logging.error(f"ブックマーク一覧から『{TARGET_FOLDER_NAME} 』フォルダを検出することが出来ませんでした")
        return

    old_sites = []

    # 3. 各サイトのRSSチェック
    for site in manga_sites:
        name = site.get("name")
        url = site.get("url")
        if not url:
            continue

        logging.info(f"→ チェック中: {name} ({url})")
        rss_url = find_rss_url(name, url)

        if rss_url:
            is_old, updated_date = is_older_than_7_days(name, rss_url)
            logging.info(f"{name}：{updated_date} : {url}")
            if is_old:
                updated_str = updated_date if updated_date else "不明"
                old_sites.append(f"{name}：{updated_str} : {url}")

    # 4. 出力
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for line in old_sites:
            f.write(line + "\n")

    logging.info(f"完了。{len(old_sites)}件のWebサイトを '{OUTPUT_FILE}' に出力しました。")

if __name__ == "__main__":
    main()
