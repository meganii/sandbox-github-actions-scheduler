import pandas as pd
import json
import os
import numpy as np
from collections import OrderedDict

# === 設定 ===
INPUT_PARQUET = "data/pages.parquet"
OUTPUT_DIR = "villagepump/pages"
OUTPUT_PATH = "data/data.jsonl"
LINE_ORDER      = ["id", "text", "userId", "created", "updated"]
TOP_LEVEL_ORDER = ["id", "title", "created", "updated", "lines"]

os.makedirs(OUTPUT_DIR, exist_ok=True)

df = pd.read_parquet(INPUT_PARQUET)
df.to_json(OUTPUT_PATH, orient="records", lines=True, force_ascii=False)

for idx, row in df.iterrows():
    row_dict = {}

    # NumPy配列をlistに変換
    for key, value in row.items():
        if isinstance(value, np.ndarray):
            row_dict[key] = value.tolist()
        else:
            row_dict[key] = value

    # "lines" の整形（順序変更）
    if "lines" in row_dict and isinstance(row_dict["lines"], list):
        reordered_lines = []
        for line in row_dict["lines"]:
            # ndarray 対応
            if isinstance(line, np.ndarray):
                line = line.tolist()
            ordered_line = OrderedDict()
            for key in LINE_ORDER:
                if key in line:
                    ordered_line[key] = line[key]
            reordered_lines.append(ordered_line)
        row_dict["lines"] = reordered_lines

    # トップレベル整形
    output_ordered = OrderedDict()
    for key in TOP_LEVEL_ORDER:
        if key in row_dict:
            output_ordered[key] = row_dict[key]

    out_path = os.path.join(OUTPUT_DIR, f"{row_dict['id']}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output_ordered, f, indent=2, ensure_ascii=False, separators=(',', ': '))

print(f"{len(df)}件のJSONを書き出しました → {OUTPUT_DIR}/")
