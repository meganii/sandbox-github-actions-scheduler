import re
import requests
import pandas as pd
import calendar

import urllib

from PIL import Image


def getSbText():
    user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
    header = {
        'User-Agent': user_agent
    }
    url = "https://scrapbox.io/api/pages/villagepump/%E3%82%A2%E3%82%AF%E3%83%86%E3%82%A3%E3%83%96%E3%83%A6%E3%83%BC%E3%82%B6%E3%83%BC%E3%81%AE%E7%A7%BB%E3%82%8A%E5%A4%89%E3%82%8F%E3%82%8A%E3%80%82/text"
    return requests.get(url, headers=header).text


def getUsersFromSbText(text):
    users = text.split('.icon]')
    users = [user.replace('[', '') for user in users if user != '']
    return users


def getTimelineDataFrameFromSbText(text):
    # Data frame
    dfName = []
    dfStart = []
    dfEnd = []

    result = re.finditer(r'^\[?(\d{4}/\d{2})\]?(.*)$', text, re.MULTILINE)
    for m in result:
        if not m:
            continue
        if m[2] == '':
            continue

        d = m[1].split('/')
        year = int(d[0])
        month = int(d[1])
        endDay = calendar.monthrange(year, month)[1]

        users = getUsersFromSbText(m[2])
        for username in users:
            dfName.append(username)
            dfStart.append(f"{year}-{month}-01")
            dfEnd.append(f"{year}-{month}-{endDay}")

    return pd.DataFrame({'Name': dfName, 'Start': dfStart,
                         "End": dfEnd}, columns=['Name', 'Start', 'End'])


def downloadFile(url, dst_path):
    try:
        header = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36"
        }
        with requests.get(url, headers=header, stream=True) as res:
            type = res.headers["content-type"]
            with open(dst_path, "wb") as f:
                [f.write(chunk)
                 for chunk in res.iter_content(chunk_size=1024) if chunk]

            if type == "image/jpeg" or type == "image/gif":
                im = Image.open(dst_path)
                im.save(dst_path)
    except requests.exceptions.RequestException as e:
        print(e)


def prepareImages(icons):
    for icon in icons:
        try:
            url = ""
            if icon == 'takker':
                url = "https://i.gyazo.com/9848f337a8da5505e8b11800fb919cd6.png"
            else:
                url = "https://scrapbox.io/api/pages/villagepump/" + \
                    urllib.parse.quote(icon) + "/icon"
            print(url)
            downloadFile(url, "./icons/" + icon + ".png")
        except:
            print(icon, "error")


def main():
    # Create data for Ganttchart
    sbText = getSbText()
    df = getTimelineDataFrameFromSbText(sbText)
    df.to_csv("./R/data.csv", index=False)

    # Prepare icon png
    prepareImages(df["Name"].unique())


if __name__ == "__main__":
    main()
