"""
publish_data.py — 从自建词频数据 (data/wordfreq, build_wordfreq.py 产出) 组装
hf-upload/VocabFreq 发布目录。

筛选：合计源头 text_bytes > 104,857,600（100 MB，1024 进制；单来源本身在构建期已 1 GiB 截断）。
输出：
  D:/code/河狸记词/data/hf-upload/VocabFreq/
    README.md      双语数据集卡片（就地维护；本脚本只重生成两个语言表格块）
    meta.json      每语 kept/coverage/sources/text_bytes/tokens_total
    files.json     全部文件的 SHA-256 校验清单
    data/small_<lang>.msgpack.gz

可重复执行：全量重建（先清空目标 data/），幂等。
卡片 README.md 不存在时报错退出（卡片以 HF 上已推送版本为基线，手工维护）。

管线顺序（详见仓库 README）：
    python scripts/tokenize_one.py <lang> <source>   # 分词 → top100k.txt
    python scripts/build_wordfreq.py                 # 全部 350 语 → data/wordfreq/（无体积筛选）
    python scripts/publish_data.py                   # 本脚本：筛选 + 组装发布目录 + 重写卡片表格
"""

import gzip
import json
import shutil
from datetime import date
from pathlib import Path

import msgpack

SRC      = Path(r"D:\code\河狸记词\data\VocabFreq\data\wordfreq")
DST      = Path(r"D:\code\河狸记词\data\hf-upload\VocabFreq")
SRC_META = SRC / "meta.json"
DST_DATA = DST / "data"
MIN_BYTES = 104_857_600  # 100 MB (1024-based): total source text across sources

NAMES = {
    "af": {"name": 'Afrikaans', "native": 'Afrikaans', "name_zh": '南非荷兰语'},
    "am": {"name": 'Amharic', "native": 'አማርኛ', "name_zh": '阿姆哈拉语'},
    "ar": {"name": 'Arabic', "native": 'العربية', "name_zh": '阿拉伯语'},
    "arz": {"name": 'Egyptian Arabic', "native": 'مصرى', "name_zh": '埃及阿拉伯语'},
    "as": {"name": 'Assamese', "native": 'অসমীয়া', "name_zh": '阿萨姆语'},
    "ast": {"name": 'Asturian', "native": 'asturianu', "name_zh": '阿斯图里亚斯语'},
    "az": {"name": 'Azerbaijani', "native": 'azərbaycan', "name_zh": '阿塞拜疆语'},
    "azb": {"name": 'South Azerbaijani', "native": 'تۆرکجه', "name_zh": '南阿塞拜疆语'},
    "ba": {"name": 'Bashkir', "native": 'башҡортса', "name_zh": '巴什基尔语'},
    "be": {"name": 'Belarusian', "native": 'беларуская', "name_zh": '白俄罗斯语'},
    "bew": {"name": 'Betawi', "native": 'Basa Betawi', "name_zh": '贝塔维语'},
    "bg": {"name": 'Bulgarian', "native": 'български', "name_zh": '保加利亚语'},
    "bn": {"name": 'Bengali', "native": 'বাংলা', "name_zh": '孟加拉语'},
    "bo": {"name": 'Tibetan', "native": 'བོད་ཡིག', "name_zh": '藏语'},
    "bs": {"name": 'Bosnian', "native": 'bosanski', "name_zh": '波斯尼亚语'},
    "ca": {"name": 'Catalan', "native": 'català', "name_zh": '加泰罗尼亚语'},
    "ce": {"name": 'Chechen', "native": 'нохчийн', "name_zh": '车臣语'},
    "ceb": {"name": 'Cebuano', "native": 'Cebuano', "name_zh": '宿务语'},
    "ckb": {"name": 'Central Kurdish', "native": 'کوردی', "name_zh": '中库尔德语'},
    "cs": {"name": 'Czech', "native": 'čeština', "name_zh": '捷克语'},
    "cy": {"name": 'Welsh', "native": 'Cymraeg', "name_zh": '威尔士语'},
    "da": {"name": 'Danish', "native": 'dansk', "name_zh": '丹麦语'},
    "de": {"name": 'German', "native": 'Deutsch', "name_zh": '德语'},
    "dv": {"name": 'Dhivehi', "native": 'ދިވެހި', "name_zh": '迪维希语'},
    "el": {"name": 'Greek', "native": 'Ελληνικά', "name_zh": '希腊语'},
    "en": {"name": 'English', "native": 'English', "name_zh": '英语'},
    "eo": {"name": 'Esperanto', "native": 'Esperanto', "name_zh": '世界语'},
    "es": {"name": 'Spanish', "native": 'español', "name_zh": '西班牙语'},
    "et": {"name": 'Estonian', "native": 'eesti', "name_zh": '爱沙尼亚语'},
    "eu": {"name": 'Basque', "native": 'euskara', "name_zh": '巴斯克语'},
    "fa": {"name": 'Persian', "native": 'فارسی', "name_zh": '波斯语'},
    "fi": {"name": 'Finnish', "native": 'suomi', "name_zh": '芬兰语'},
    "fr": {"name": 'French', "native": 'français', "name_zh": '法语'},
    "fy": {"name": 'West Frisian', "native": 'Frysk', "name_zh": '西弗里西亚语'},
    "ga": {"name": 'Irish', "native": 'Gaeilge', "name_zh": '爱尔兰语'},
    "gl": {"name": 'Galician', "native": 'galego', "name_zh": '加利西亚语'},
    "gmh": {"name": 'Middle High German', "native": 'Mittelhochdeutsch', "name_zh": '中古高地德语'},
    "gu": {"name": 'Gujarati', "native": 'ગુજરાતી', "name_zh": '古吉拉特语'},
    "ha": {"name": 'Hausa', "native": 'Harshen Hausa', "name_zh": '豪萨语'},
    "he": {"name": 'Hebrew', "native": 'עברית', "name_zh": '希伯来语'},
    "hi": {"name": 'Hindi', "native": 'हिन्दी', "name_zh": '印地语'},
    "hr": {"name": 'Croatian', "native": 'hrvatski', "name_zh": '克罗地亚语'},
    "hu": {"name": 'Hungarian', "native": 'magyar', "name_zh": '匈牙利语'},
    "hy": {"name": 'Armenian', "native": 'հայերեն', "name_zh": '亚美尼亚语'},
    "id": {"name": 'Indonesian', "native": 'Bahasa Indonesia', "name_zh": '印度尼西亚语'},
    "ig": {"name": 'Igbo', "native": 'Asụsụ Igbo', "name_zh": '伊博语'},
    "is": {"name": 'Icelandic', "native": 'íslenska', "name_zh": '冰岛语'},
    "it": {"name": 'Italian', "native": 'italiano', "name_zh": '意大利语'},
    "ja": {"name": 'Japanese', "native": '日本語', "name_zh": '日语'},
    "ka": {"name": 'Georgian', "native": 'ქართული', "name_zh": '格鲁吉亚语'},
    "kk": {"name": 'Kazakh', "native": 'қазақша', "name_zh": '哈萨克语'},
    "km": {"name": 'Khmer', "native": 'ខ្មែរ', "name_zh": '高棉语'},
    "kn": {"name": 'Kannada', "native": 'ಕನ್ನಡ', "name_zh": '卡纳达语'},
    "ko": {"name": 'Korean', "native": '한국어', "name_zh": '韩语'},
    "ku": {"name": 'Kurdish', "native": 'kurdî', "name_zh": '库尔德语'},
    "ky": {"name": 'Kyrgyz', "native": 'кыргызча', "name_zh": '吉尔吉斯语'},
    "la": {"name": 'Latin', "native": 'Latina', "name_zh": '拉丁语'},
    "lb": {"name": 'Luxembourgish', "native": 'Lëtzebuergesch', "name_zh": '卢森堡语'},
    "lo": {"name": 'Lao', "native": 'ພາສາລາວ', "name_zh": '老挝语'},
    "lt": {"name": 'Lithuanian', "native": 'lietuvių', "name_zh": '立陶宛语'},
    "lv": {"name": 'Latvian', "native": 'latviešu', "name_zh": '拉脱维亚语'},
    "mg": {"name": 'Malagasy', "native": 'Malagasy', "name_zh": '马达加斯加语'},
    "mk": {"name": 'Macedonian', "native": 'македонски', "name_zh": '马其顿语'},
    "ml": {"name": 'Malayalam', "native": 'മലയാളം', "name_zh": '马拉雅拉姆语'},
    "mn": {"name": 'Mongolian', "native": 'монгол', "name_zh": '蒙古语'},
    "mr": {"name": 'Marathi', "native": 'मराठी', "name_zh": '马拉地语'},
    "ms": {"name": 'Malay', "native": 'Bahasa Melayu', "name_zh": '马来语'},
    "mt": {"name": 'Maltese', "native": 'Malti', "name_zh": '马耳他语'},
    "my": {"name": 'Myanmar', "native": 'မြန်မာ', "name_zh": '缅甸语'},
    "nb": {"name": 'Norwegian Bokmål', "native": 'norsk bokmål', "name_zh": '书面挪威语'},
    "ne": {"name": 'Nepali', "native": 'नेपाली', "name_zh": '尼泊尔语'},
    "new": {"name": 'Newari', "native": 'नेपाल भाषा', "name_zh": '尼瓦尔语'},
    "nl": {"name": 'Dutch', "native": 'Nederlands', "name_zh": '荷兰语'},
    "nn": {"name": 'Norwegian Nynorsk', "native": 'norsk nynorsk', "name_zh": '新挪威语'},
    "no": {"name": 'Norwegian', "native": 'norsk', "name_zh": '挪威语'},
    "nrm": {"name": 'Norman', "native": 'Normaund', "name_zh": '诺曼语'},
    "oc": {"name": 'Occitan', "native": 'occitan', "name_zh": '奥克语'},
    "or": {"name": 'Odia', "native": 'ଓଡ଼ିଆ', "name_zh": '奥里亚语'},
    "pa": {"name": 'Punjabi', "native": 'ਪੰਜਾਬੀ', "name_zh": '旁遮普语'},
    "pl": {"name": 'Polish', "native": 'polski', "name_zh": '波兰语'},
    "pnb": {"name": 'Western Punjabi', "native": 'پنجابی', "name_zh": '西旁遮普语'},
    "ps": {"name": 'Pashto', "native": 'پښتو', "name_zh": '普什图语'},
    "pt": {"name": 'Portuguese', "native": 'português', "name_zh": '葡萄牙语'},
    "ro": {"name": 'Romanian', "native": 'română', "name_zh": '罗马尼亚语'},
    "ru": {"name": 'Russian', "native": 'русский', "name_zh": '俄语'},
    "sd": {"name": 'Sindhi', "native": 'سنڌي', "name_zh": '信德语'},
    "sh": {"name": 'Serbo-Croatian', "native": 'srpskohrvatski', "name_zh": '塞尔维亚-克罗地亚语'},
    "si": {"name": 'Sinhala', "native": 'සිංහල', "name_zh": '僧伽罗语'},
    "simple": {"name": 'Simple English', "native": 'Simple English', "name_zh": '简明英语'},
    "sk": {"name": 'Slovak', "native": 'slovenčina', "name_zh": '斯洛伐克语'},
    "sl": {"name": 'Slovenian', "native": 'slovenščina', "name_zh": '斯洛文尼亚语'},
    "so": {"name": 'Somali', "native": 'Soomaaliga', "name_zh": '索马里语'},
    "sq": {"name": 'Albanian', "native": 'shqip', "name_zh": '阿尔巴尼亚语'},
    "sr": {"name": 'Serbian', "native": 'српски', "name_zh": '塞尔维亚语'},
    "sv": {"name": 'Swedish', "native": 'svenska', "name_zh": '瑞典语'},
    "sw": {"name": 'Swahili', "native": 'Kiswahili', "name_zh": '斯瓦希里语'},
    "ta": {"name": 'Tamil', "native": 'தமிழ்', "name_zh": '泰米尔语'},
    "te": {"name": 'Telugu', "native": 'తెలుగు', "name_zh": '泰卢固语'},
    "tg": {"name": 'Tajik', "native": 'тоҷикӣ', "name_zh": '塔吉克语'},
    "th": {"name": 'Thai', "native": 'ไทย', "name_zh": '泰语'},
    "tl": {"name": 'Tagalog', "native": 'Tagalog', "name_zh": '他加禄语'},
    "tr": {"name": 'Turkish', "native": 'Türkçe', "name_zh": '土耳其语'},
    "tt": {"name": 'Tatar', "native": 'татарча', "name_zh": '塔塔尔语'},
    "ug": {"name": 'Uyghur', "native": 'ئۇيغۇرچە', "name_zh": '维吾尔语'},
    "uk": {"name": 'Ukrainian', "native": 'українська', "name_zh": '乌克兰语'},
    "ur": {"name": 'Urdu', "native": 'اردو', "name_zh": '乌尔都语'},
    "uz": {"name": 'Uzbek', "native": 'oʻzbekcha', "name_zh": '乌兹别克语'},
    "vi": {"name": 'Vietnamese', "native": 'Tiếng Việt', "name_zh": '越南语'},
    "war": {"name": 'Waray', "native": 'Winaray', "name_zh": '瓦瑞语'},
    "yi": {"name": 'Yiddish', "native": 'ייִדיש', "name_zh": '意第绪语'},
    "zh": {"name": 'Chinese', "native": '中文', "name_zh": '中文'},
}


BUILD_TAG = "v7"
THRESH_DESC = "total source text_bytes > 104,857,600 bytes (100 MB)"


# ---------- utilities ----------

def read_msgpack_gz(path):
    with gzip.open(path, "rb") as f:
        return msgpack.unpackb(f.read(), raw=False)


def fmt_int(n):
    return f"{n:,}"


def human_mb(n):
    return f"{n / 1048576:.1f} MB"


# ---------- card table blocks ----------

M_TABLE_EN = ("<!-- BEGIN GENERATED LANGUAGE TABLE -- run `python scripts/publish_data.py` -->",
              "<!-- END GENERATED LANGUAGE TABLE -->")
M_TABLE_ZH = ("<!-- BEGIN GENERATED LANGUAGE TABLE ZH -- run `python scripts/publish_data.py` -->",
              "<!-- END GENERATED LANGUAGE TABLE ZH -->")

TABLE_HEAD = ("| code | language | native name | first word | cb | float | words | cumulative coverage |\n"
              "|------|----------|-------------|------------|----|-------|-------|---------------------|")


def make_tables(rows):
    lines_en, lines_zh = [TABLE_HEAD], [TABLE_HEAD]
    total_words = 0
    for r in rows:
        total_words += r["kept"]
        tail = (r["first_word"], str(r["top_cb"]), f"{r['top_float']:.2e}",
                fmt_int(r["kept"]), f"{r['coverage'] * 100:.1f}%")
        lines_en.append(f"| {r['code']} | {r['name']} | {r['native']} | " + " | ".join(tail) + " |")
        lines_zh.append(f"| {r['code']} | {r['name_zh']} | {r['native']} | " + " | ".join(tail) + " |")
    lines_en.append(f"| *Total* | *{len(rows)} languages* | — | — | — | — | *{fmt_int(total_words)}* | — |")
    lines_zh.append(f"| *合计* | *{len(rows)} 种语言* | — | — | — | — | *{fmt_int(total_words)}* | — |")
    return "\n".join(lines_en) + "\n", "\n".join(lines_zh) + "\n", total_words


def replace_block(text, markers, block):
    begin, end = markers
    i = text.index(begin)
    j = text.index(end) + len(end)
    return text[:i] + begin + "\n" + block.rstrip("\n") + "\n" + end + text[j:]


# ---------- main ----------

def main():
    meta = json.loads(SRC_META.read_text(encoding="utf-8"))
    langs = meta["languages"]

    selected = []
    for code, lm in langs.items():
        total_bytes = sum(s["text_bytes"] for s in lm["sources"].values())
        if total_bytes > MIN_BYTES:
            selected.append((code, total_bytes))
    selected.sort(key=lambda x: x[0])
    codes = [c for c, _ in selected]
    print(f"selected {len(codes)} / {len(langs)} languages "
          f"(total source text_bytes > {MIN_BYTES})")

    # sync data files
    if DST_DATA.exists():
        shutil.rmtree(DST_DATA)
    DST_DATA.mkdir(parents=True)
    rows = []
    for code in codes:
        src_file = SRC / "data" / f"small_{code}.msgpack.gz"
        dst_file = DST_DATA / f"small_{code}.msgpack.gz"
        shutil.copy2(src_file, dst_file)

        doc = read_msgpack_gz(dst_file)
        header, bands = doc[0], doc[1:]
        coverage = sum(len(band) * 10 ** (-b / 100) for b, band in enumerate(bands))
        top_cb = next(b for b, band in enumerate(bands) if band)
        first = bands[top_cb][0]
        nm = NAMES[code]
        rows.append({
            "code": code,
            "name": nm["name"],
            "name_zh": nm["name_zh"],
            "native": nm["native"],
            "first_word": first,
            "top_cb": top_cb,
            "top_float": 10 ** (-top_cb / 100),
            "kept": sum(len(b) for b in bands),
            "coverage": coverage,
        })
    print(f"  synced {len(rows)} data files")

    table_en, table_zh, total_words = make_tables(rows)
    total_size = human_mb(sum(f.stat().st_size for f in DST_DATA.iterdir()))

    # meta.json
    out_meta = {
        "dataset": "VocabFreq",
        "version": BUILD_TAG,
        "generated_at": date.today().isoformat(),
        "selection": {
            "rule": THRESH_DESC,
            "unit": "bytes (1024-based MB)",
            "threshold_bytes": MIN_BYTES,
        },
        "sources_note": "per-source text_bytes/tokens as recorded by build_wordfreq; "
                        "single sources are capped at 1 GiB of text during the build",
        "languages": {},
    }
    for code in codes:
        lm = langs[code]
        row = next(r for r in rows if r["code"] == code)
        out_meta["languages"][code] = {
            "kept": row["kept"],
            "coverage": row["coverage"],
            "sources": {s: {"text_bytes": v["text_bytes"], "tokens": v["tokens"]}
                        for s, v in lm["sources"].items()},
            "text_bytes": sum(v["text_bytes"] for v in lm["sources"].values()),
            "tokens_total": sum(v["tokens"] for v in lm["sources"].values()),
        }
    (DST / "meta.json").write_text(
        json.dumps(out_meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # README card: tables regenerated in place; card text is hand-maintained
    card = DST / "README.md"
    if not card.exists():
        raise FileNotFoundError(
            f"{card} not found — restore the card from "
            f"https://huggingface.co/datasets/vocabradar/VocabFreq first")
    text = card.read_text(encoding="utf-8")
    text = replace_block(text, M_TABLE_EN, table_en)
    text = replace_block(text, M_TABLE_ZH, table_zh)
    card.write_text(text, encoding="utf-8")

    # files.json: sha256 of every published file
    import hashlib

    def sha256(path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    entries = []
    for p in sorted(DST.rglob("*")):
        if p.is_file() and p.name != "files.json":
            entries.append({"file": str(p.relative_to(DST)).replace("\\", "/"),
                            "bytes": p.stat().st_size,
                            "sha256": sha256(p)})
    (DST / "files.json").write_text(json.dumps({
        "generatedAt": date.today().isoformat(), "algorithm": "sha256",
        "files": entries}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"done: {len(codes)} langs, {fmt_int(total_words)} words, {total_size}")


if __name__ == "__main__":
    main()
