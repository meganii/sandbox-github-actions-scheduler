#!/bin/sh

FILE=$1

sed -i "$ s/,$//" $FILE      # ファイル最終行の,を削除
sed -i '1i{"pages":[' $FILE  # ファイル先頭行にKey"pages"を追加
sed -i '$a]}' $FILE          # ファイル最終行にjsonの閉じ括弧を追加