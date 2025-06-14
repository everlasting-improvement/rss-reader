import json
import os
import datetime
import requests
import feedparser
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import logging

# ログファイルとログレベルの設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler("rss_reader.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)


# --- 設定 ---
BOOKMARKS_PATH = os.path.expanduser(
    r'C:\Users\<User name>\AppData\Local\Google\Chrome\User Data\Default\Bookmarks'  # You need to configure it before execution
)
TARGET_FOLDER_NAME = "web-manga" # You need to configure it before execution
OUTPUT_FILE = "recent_feeds.txt"

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
        headers = {
           "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/137.0.0.0 Safari/537.36"
            )
        }
        res = requests.get(site_url, headers=headers, timeout=10)
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

def is_older_than_7_days(name, feed_url):
    try:
        parsed = feedparser.parse(feed_url)
        entries = parsed.entries
        if not entries:
            return True, None
        latest = entries[0].get("published_parsed") or entries[0].get("updated_parsed")
        if not latest:
            return True, None
        latest_date = datetime.datetime(*latest[:6])
        delta = datetime.datetime.now() - latest_date
        return delta.days <= 7, latest_date.strftime("%Y-%m-%d")
    except Exception as e:
        logging.exception(f"[!] フィード解析失敗: {name} : {feed_url} ({e})")
        return True, None

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
