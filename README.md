# rss-reader
Extract RSS feeds from your bookmarks, parse them, and output URLs to .txt file if they have been updated recently.

# Detailed process
1. Access to your Google Chrome's bookmark folder named "web-manga"
2. Extract bookmarked Web sites' name and URL
3. Execute HTTP request to the URLs, and identify their RSS-feed's URLs
4. Parse the RSS-feeds, and check if they have been updated in rencent 7 days
5. If YES, then output their name, last-updated-date, and URL to recent_feeds.txt

# How to run
## 1st time
```
pip install requests beautifulsoup4
python rss-reader.py
```
## From 2nd time onwards
```
python rss-reader.py
```

# notes
The location of the Google Chrome's bookmark folder depends on your Oerating System.
You may need to adjust its path by your self.
If you're using Windows, it is
```
C:\Users\<User name>\AppData\Local\Google\Chrome\User Data\Default\Bookmarks
```
If you're using macOS, it is
```
~/Library/Application Support/Google/Chrome/Default/Bookmarks
```
