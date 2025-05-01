import requests
import sys

OWNER = "meganii"
REPO = "sandbox-github-actions-scheduler"
FILENAME = "pages.parquet"
DIST = "data"

# GitHub API: 最新リリース取得
url = f"https://api.github.com/repos/{OWNER}/{REPO}/releases/latest"
response = requests.get(url)
response.raise_for_status()
data = response.json()

# アセットのURL検索
asset_url = None
for asset in data.get("assets", []):
    if asset["name"] == FILENAME:
        asset_url = asset["browser_download_url"]
        break

if not asset_url:
    print(f"Asset '{FILENAME}' not found in latest release.")
    sys.exit(1)

# ダウンロード処理
download_response = requests.get(asset_url)
with open(f"{DIST}/{FILENAME}", "wb") as f:
    f.write(download_response.content)

print(f"Downloaded: {FILENAME}")
