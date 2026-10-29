#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_wordfreq.py — 把 F:/data/WordFrequency/wordfreq 的 top100k.txt (pyicu 分词产出)
转成 hf-upload/VocabFreq 同款 cB-msgpack 格式，写入 D:/code/河狸记词/data/VocabFreq/data/wordfreq/。

数据源：本仓库 pyicu BreakIterator 分词结果（wiki ≥1GiB / fw2 ≥1GiB）
语言：Python（不依赖 Node）
清理：借鉴 clean.js 思想，覆盖 354 语全部 Unicode script 白名单
th：本统一管线产出（原 th_pipeline.py 弃用）
收录：全量语种（不做体积筛选，meta 带全体积字段供下游筛选）；词门槛 fu_w>1e-6 且 fu_w/word_bytes>2e-7

输出结构：
  D:/code/河狸记词/data/VocabFreq/data/wordfreq/
    meta.json
    data/small_<lang>.msgpack.gz   [header, band_0..band_699]  cB 格式
"""
import gzip, json, math, re, time, unicodedata
from pathlib import Path
from collections import Counter, defaultdict

import msgpack

# ── I/O ─────────────────────────────────────────────────────
FF         = Path(r"F:\data\WordFrequency\wordfreq")
OUT_BASE   = Path(r"D:\code\河狸记词\data\VocabFreq\data\wordfreq")
OUT_DATA   = OUT_BASE / "data"
ONE_GIB    = 1024 ** 3
CB_MAX     = 700  # cB 带数：band_k 收录 cB=k 的词（fu≈1e-(k/100)）
FREQ_CUT   = 2e-7  # 产品阈值：fu_w / word_bytes > 2e-7（另加 fu_w > 1e-6 双门槛）
N_BANDS    = CB_MAX  # 1 cB 分辨率

# meta.json 中 sources 使用的源头全名（与 F:/data/corpus 目录名一致）
FULL_SRC = {
    "wikipedia": "wikipedia-monthly",
    "ultrafineweb_l3": "Ultra-FineWeb-L3",
    "fineweb2_hq_plus": "FineWeb2-HQ-plus",
}

# ── BCP-47 → iso 映射 ───────────────────────────────────────
BCP47 = {
    "en":"en","zh":"zh","afr_Latn":"af","als_Latn":"sq","amh_Ethi":"am","arb_Arab":"ar",
    "ars_Arab":"ar","ary_Arab":"ar","arz_Arab":"ar","asm_Beng":"as","azj_Latn":"az",
    "bel_Cyrl":"be","ben_Beng":"bn","bew_Latn":"bew","bod_Tibt":"bo","bos_Latn":"bs",
    "bul_Cyrl":"bg","cat_Latn":"ca","ces_Latn":"cs","ckb_Arab":"ckb","cmn_Hani":"zh",
    "cym_Latn":"cy","dan_Latn":"da","deu_Latn":"de","div_Thaa":"dv","ell_Grek":"el",
    "eng_Latn":"en","epo_Latn":"eo","est_Latn":"et","eus_Latn":"eu","fao_Latn":"fo",
    "fas_Arab":"fa","fil_Latn":"fil","fin_Latn":"fi","fra_Latn":"fr","fry_Latn":"fy",
    "gle_Latn":"ga","glg_Latn":"gl","gmh_Latn":"gmh","guj_Gujr":"gu","heb_Hebr":"he",
    "hif_Latn":"hif","hin_Deva":"hi","hrv_Latn":"hr","hun_Latn":"hu","hye_Armn":"hy",
    "ind_Latn":"id","isl_Latn":"is","ita_Latn":"it","jav_Latn":"jv","jpn_Jpan":"ja",
    "kan_Knda":"kn","kat_Geor":"ka","kaz_Cyrl":"kk","khk_Cyrl":"mn","khm_Khmr":"km",
    "kir_Cyrl":"ky","kmr_Latn":"ku","kor_Hang":"ko","lao_Laoo":"lo","lat_Latn":"la",
    "lav_Latn":"lv","lit_Latn":"lt","ltz_Latn":"lb","lvs_Latn":"lv","mal_Mlym":"ml",
    "mar_Deva":"mr","mkd_Cyrl":"mk","mlt_Latn":"mt","mon_Cyrl":"mn","mri_Latn":"mi",
    "msa_Latn":"ms","mya_Mymr":"my","mya_Mmymr":"my","nep_Deva":"ne","nld_Latn":"nl",
    "nno_Latn":"nn","nob_Latn":"nb","npi_Deva":"ne","nrm_Latn":"nrm","ori_Orya":"or",
    "ory_Orya":"or","pan_Guru":"pa","pbt_Arab":"ps","plt_Latn":"mg","pol_Latn":"pl",
    "por_Latn":"pt","pus_Arab":"ps","ron_Latn":"ro","rus_Cyrl":"ru","sin_Sinh":"si",
    "slk_Latn":"sk","slv_Latn":"sl","sna_Latn":"sn","snd_Arab":"sd","som_Latn":"so",
    "spa_Latn":"es","sqi_Latn":"sq","srp_Cyrl":"sr","srp_Latn":"sr","swa_Latn":"sw",
    "swe_Latn":"sv","swh_Latn":"sw","tam_Taml":"ta","tat_Cyrl":"tt","tel_Telu":"te",
    "tgk_Cyrl":"tg","tha_Thai":"th","tgl_Latn":"fil","tur_Latn":"tr","uig_Arab":"ug",
    "ukr_Cyrl":"uk","urd_Arab":"ur","uzn_Cyrl":"uz","uzn_Latn":"uz","uzb_Latn":"uz",
    "vie_Latn":"vi","xho_Latn":"xh","ydd_Hebr":"yi","yid_Hebr":"yi","yor_Latn":"yo",
    "zho_Hant":"zh-Hant","zsm_Latn":"ms","zul_Latn":"zu",
    "ultrafineweb_en_l3":"en","ultrafineweb_zh_l3":"zh",
    "ekk_Latn":"et",  # Estonian (fine-grained code in fw2)
    "tl":"fil",  # 旧 Tagalog wiki 目录名/旧语言代码 → 统一用 ISO 639-3 的 fil
}
def norm(code): return BCP47.get(code, code)

# ── Unicode letter range → script code ──────────────────────
RAW_RANGES = [
    ("Latn", [(0x41,0x5a),(0x61,0x7a),(0xc0,0x24f),(0x1e00,0x1eff),(0x2c60,0x2c7f),(0xa720,0xa7ff),(0xab30,0xab6f)]),
    ("Grek", [(0x370,0x3ff),(0x1f00,0x1fff)]),
    ("Cyrl", [(0x400,0x52f),(0x2de0,0x2dff),(0xa640,0xa69f)]),
    ("Hebr", [(0x590,0x5ff)]),
    ("Arab", [(0x600,0x6ff),(0x750,0x77f),(0x8a0,0x8ff),(0xfb50,0xfdff),(0xfe70,0xfeff)]),
    ("Deva", [(0x900,0x97f)]),
    ("Beng", [(0x980,0x9ff)]),
    ("Guru", [(0xa00,0xa7f)]),
    ("Gujr", [(0xa80,0xaff)]),
    ("Orya", [(0xb00,0xb7f)]),
    ("Taml", [(0xb80,0xbff)]),
    ("Telu", [(0xc00,0xc7f)]),
    ("Knda", [(0xc80,0xcff)]),
    ("Mlym", [(0xd00,0xd7f)]),
    ("Sinh", [(0xd80,0xdff)]),
    ("Thai", [(0xe00,0xe7f)]),
    ("Laoo", [(0xe80,0xeff)]),
    ("Tibt", [(0xf00,0xfff)]),
    ("Mymr", [(0x1000,0x109f),(0xa9e0,0xa9ff)]),
    ("Geor", [(0x10a0,0x10ff)]),
    ("Hang", [(0xac00,0xd7af),(0x1100,0x11ff),(0x3130,0x318f)]),
    ("Ethi", [(0x1200,0x137f),(0x1380,0x139f),(0x2d80,0x2ddf),(0xab00,0xab2f)]),
    ("Cher", [(0x13a0,0x13ff),(0xab70,0xabbf)]),
    ("Cans", [(0x1400,0x167f)]),
    ("Ogam", [(0x1680,0x169f)]),
    ("Runr", [(0x16a0,0x16ff)]),
    ("Hani", [(0x3400,0x4dbf),(0x4e00,0x9fff),(0xf900,0xfaff),(0x20000,0x2a6df)]),
    ("Hira", [(0x3040,0x309f)]),
    ("Kana", [(0x30a0,0x30ff),(0x31f0,0x31ff),(0xff66,0xff9d)]),
    ("Khmr", [(0x1780,0x17ff),(0x19e0,0x19ff)]),
    ("Armn", [(0x530,0x58f)]),
    ("Syrc", [(0x700,0x74f)]),
    ("Thaa", [(0x780,0x7bf)]),
    ("Nkoo", [(0x7c0,0x7ff)]),
    ("Mtei", [(0xabc0,0xabff)]),
    ("Phag", [(0xa840,0xa87f)]),
    ("Lisu", [(0xa4d0,0xa4ff)]),
    ("Bamu", [(0xa6a0,0xa6ff)]),
]
_cp_map = {}
for _s, _ranges in RAW_RANGES:
    for _lo, _hi in _ranges:
        for _cp in range(_lo, _hi + 1):
            try:
                _c = unicodedata.category(chr(_cp))
            except ValueError:
                continue
            if _c.startswith("L") and _cp not in _cp_map:
                _cp_map[_cp] = _s
def cp_script(cp):
    return _cp_map.get(cp)
LETTER_SCRIPTS = {s for s, _ in RAW_RANGES} | {"Other"}

LANG_SCRIPTS = {
    # Arabic
    "ar":{"Arab"},"fa":{"Arab"},"ur":{"Arab"},"ckb":{"Arab"},"ps":{"Arab"},
    "sd":{"Arab"},"arz":{"Arab"},"azb":{"Arab"},"ug":{"Arab"},
    "pnb":{"Arab"},"skr":{"Arab"},"ks":{"Arab"},
    # Bengali
    "bn":{"Beng"},"as":{"Beng"},
    # Cyrillic
    "bg":{"Cyrl"},"mk":{"Cyrl"},"ru":{"Cyrl"},"uk":{"Cyrl"},"kk":{"Cyrl"},
    "sr":{"Cyrl"},"be":{"Cyrl"},"ky":{"Cyrl"},"tg":{"Cyrl"},"mn":{"Cyrl"},
    "ce":{"Cyrl"},"ba":{"Cyrl"},"tt":{"Cyrl"},"udm":{"Cyrl"},"av":{"Cyrl"},
    "cv":{"Cyrl"},"os":{"Cyrl"},"ab":{"Cyrl"},"sah":{"Cyrl"},
    # Greek
    "el":{"Grek"},
    # Hebrew
    "he":{"Hebr"},"yi":{"Hebr"},
    # Devanagari (Hindi/Marathi/Nepali/Sanskrit)
    "hi":{"Deva"},"mr":{"Deva"},"ne":{"Deva"},"sa":{"Deva"},"mai":{"Deva"},
    # Meitei (Meitei Mayek, 兼有孟加拉文转写)
    "mni":{"Mtei","Beng"},
    # Divehi
    "dv":{"Thaa"},
    # South/Brahmic
    "ta":{"Taml"},"te":{"Telu"},"si":{"Sinh"},"gu":{"Gujr"},"pa":{"Guru"},
    "or":{"Orya"},"ml":{"Mlym"},"kn":{"Knda"},
    # Georgian / Armenian
    "ka":{"Geor"},"hy":{"Armn"},
    # CJK
    "zh":{"Hani"},"zh-Hant":{"Hani"},"ja":{"Hani","Hira","Kana"},"ko":{"Hang"},
    # SE Asian
    "th":{"Thai"},"lo":{"Laoo"},"my":{"Mymr"},"km":{"Khmr"},"bo":{"Tibt"},
    # Ethiopic
    "am":{"Ethi"},"ti":{"Ethi"},
    # Latin-only but common — leave as default; listed here only for clarity
    # all other langs fall through to DEFAULT_SCRIPTS = {"Latn"}
}
DEFAULT_SCRIPTS = {"Latn"}

KEEP_DIACRITIC_SINGLE = {
    "fr","es","it","pt","ca","da","nb","is","sv","vi","en","de","nl","pl","cs",
    "sk","sl","hr","hu","ro","lt","lv","id","ms","af","sq",
}
# wordfreq 原版：tr/az/kk 用 dotless_i casefold（I→ı, İ→i）
DOTLESS_I_LANGS = {"tr", "az", "kk"}
# wordfreq 原版：ro 把 cedilla ș/ț 转成 comma below
CEDILLA_TO_COMMA_LANGS = {"ro"}
# wordfreq 原版：阿拉伯/希伯来/波斯/乌尔都等 abjad 去掉元音点
ABJAD_MARKS_REMOVED = {"ar", "he", "fa", "ur", "ps", "sd", "ug", "ku", "ms-arab"}
# wordfreq 原版：脚本决定 normal_form —— Latn/Grek/Cyrillic → NFC，其余 → NFKC
NFC_SCRIPTS = {"Latn", "Grek", "Cyrl"}
# 书写时词间有空格的语言：word_bytes 需 +1 计入空格代价
# 表意/单音节约文字（中日韩蒙藏缅泰老高棉）无词间空格，不加
SPACE_WORD_LANGS = {
    # 拉丁系
    "en","es","fr","de","pt","it","nl","pl","cs","sk","sl","hr","hu","ro","da","sv","nb","is","fi","et","lt","lv",
    "ca","gl","sq","sr","bs","tr","az","id","ms","vi","af","sw","zu","xh","fil","jv","eu","br","co","wa","lb","fo",
    "nn","ia","sa","la","kw","ga","cy","gd","mt",
    # 西里尔系
    "bg","uk","ru","mk","be","kk","ky","tg","uz","tk","ba","os","av","ce","ab",
    "tt","udm","cv","sah",
    # 希腊
    "el",
    # 阿拉伯系（词间有空格）
    "ar","fa","ur","ps","sd","ku","tt-arab","ug","arz","ckb",
    "azb","pnb","skr","ks",
    # 印度系（天城/婆罗米系有词间空格）
    "hi","mr","ne","bn","pa","gu","or","ta","te","kn","ml","si","as","sa","kok","ks",
    "mai",
    # 格鲁吉亚 / 亚美尼亚
    "ka","hy",
    # 埃塞俄比亚（用 ፡ 分隔词，+1 模拟间距）
    "am","ti","om",
}
NO_SPACE_WORD_LANGS = {
    "zh","zh-Hant","ja","ko","th","lo","my","km","bo","dz","mn","ii",
}

_MARK_RE = None  # 懒加载 regex


def _get_mark_re():
    """匹配 combining marks (Mn) —— 包括希伯来 niqqud、阿拉伯 tashkeel 等"""
    global _MARK_RE
    if _MARK_RE is None:
        import re
        _MARK_RE = re.compile(r'[\u0300-\u036f\u0591-\u05bd\u05bf\u05c1\u05c2\u05c4\u05c5\u05c7\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06dc\u06df-\u06e4\u06e7\u06e8\u06ea-\u06ed\u0711\u0730-\u074a\u07a6-\u07b0\u07eb-\u07f3\u0816-\u0819\u081b-\u0823\u0825-\u0827\u0829-\u082d\u0859-\u085b\u08e3-\u0903\u093a-\u093c\u093e-\u094f\u0951-\u0957\u0962\u0963]')
    return _MARK_RE


def is_diacritic_single(word):
    """len==1 的非 ASCII 拉丁带音符字母（â/ó/ñ）；对白名单语种豁免"""
    if len(word) != 1: return False
    cp = ord(word)
    if cp <= 0x7f: return False
    return cp_script(cp) == "Latn"


def _normalize_word(word, lang):
    """wordfreq 原版规范化流水线：NFKC/NFC → 去元音点 → casefold → diacritics fix"""
    # 1) Unicode 规范化（语种主写脚本决定 NFC 或 NFKC）
    main_script = next((s for s in LANG_SCRIPTS.get(lang, set()) if s != "Other"), None)
    if main_script in NFC_SCRIPTS:
        word = unicodedata.normalize("NFC", word)
    else:
        word = unicodedata.normalize("NFKC", word)

    # 2) Abjad 去元音点
    if lang in ABJAD_MARKS_REMOVED:
        word = _get_mark_re().sub("", word)

    # 3) Casefold（tr/az/kk 用 dotless_i 特殊处理）
    if lang in DOTLESS_I_LANGS:
        # İ → i，I → ı，然后正常 casefold
        word = unicodedata.normalize("NFC", word).replace("İ", "i").replace("I", "ı")
        word = word.casefold()
    else:
        word = word.casefold()

    # 4) Cedilla ↔ comma 修复
    if lang in CEDILLA_TO_COMMA_LANGS:
        word = word.replace("ş", "ș").replace("ţ", "ț")

    return word


def clean_one(word, lang, allowed, keep_diac):
    """返回 (normalized_word, None) 表示保留；返回 (None, reason) 表示剔除。
    normalized_word 已经 NFKC + casefold，可直接作为 counter 的 key。
    reason 是统计用的剔除类型：'no_letter' / 'numeric' / 'diacritic_single' / 'foreign'。
    规范化流水线（对齐 wordfreq 原版 preprocess_text）：
      NFKC/NFC → Abjad 去元音点 → casefold（tr/az/kk dotless_i）→ cedilla 修复"""
    # ── 0. Unicode 规范化（语种专属：NFC/NFKC + 去 mark + casefold + diacritics）──
    word = _normalize_word(word, lang)

    # ── 1. 词必须非空，第一个字符必须是字母 (Lo/Lu/Ll/Lt/Lm) ──
    #    汉字 (Lo)、假名 (Lo) 一二三(Lo) 都是字母，数字(Nd/Nl/No) 符号(S*) 标点(P*) 剔除
    if not word: return None, "no_letter"
    first_cat = unicodedata.category(word[0])
    if first_cat.startswith("N"): return None, "numeric"
    if not first_cat.startswith("L"): return None, "no_letter"

    # ── 1b. 词干含 ASCII 0-9 数字 → 剔除（mp3, km2, x86, co2, a320, f1, ipv6, b12, 2023 ...） ──
    #     Unicode 各文种专属数字（༡၁១૧١۱১ধ二等）是正常文字，不剔除
    if re.search(r"[0-9]", word):
        return None, "has_digit"

    # ── 1c. 含常见域名 TLD → 剔除（example.com example.org net.wikipedia.org ...） ──
    if re.search(r"\.(com|org|net|edu|gov|io|info|biz|xyz|tk|mil|int)\b", word):
        return None, "domain_tld"

    # ── 2. 单非 ASCII 拉丁带音符字母（â、ó），对白名单语种豁免 ──
    if is_diacritic_single(word) and not keep_diac: return None, "diacritic_single"

    # ── 3. script 检测：词的任何书写系统不在本语种白名单里 = 外来词 ──
    scripts = set()
    for ch in word:
        cat = unicodedata.category(ch)
        if cat.startswith("N"): continue                       # 跳过数字（词中数字不剔除）
        if cat in ("Mn", "Mc", "Me", "Cf"): continue            # 跳过 mark
        if cat.startswith("L"):
            scripts.add(cp_script(ord(ch)) or "Other")
    for s in scripts:
        if s not in allowed and s != "Other": return None, "foreign"

    # ── 4. 拉丁语种里出现常见英语借词/代码碎片（仅 tr/id）──
    if "Latn" in allowed and lang in _LATIN_FOREIGN and word in _LATIN_FOREIGN[lang]:
        return None, "foreign"

    return word, None

# 拉丁语种外来词黑名单（含 HTML/CSS/JS 代码碎片——只对 tr/id 等非英语拉丁语种）
_LATIN_FOREIGN = {
    "tr": {"the","of","in","to","and","is","for","on","with","at","from","by","it","this",
           "that","are","be","or","an","as","was","but","not","have","has","had","will","can",
           "its","he","she","them","they","their","his","her","my","your","our","do","does",
           "did","been","being","if","then","than","into","about","up","down","out","all",
           "some","any","no","more","most","other","such","only","also","just","so","very",
           "too","how","what","which","who","when","where","why","new","old","first","last",
           "long","great","little","center","align","class","style","display","position",
           "width","font","color","http","table","return","function","null","left","right",
           "source","height","nbsp","www"},
    "id": {"the","of","and","is","in","to","for","on","with","at","from","by","it","this",
           "that","are","be","or","an","as","was","but","not","have","has","had","will","can",
           "he","she","them","they","their","his","her","my","your","our","do","does","did",
           "been","being","if","then","than","into","about","all","some","any","more","most",
           "other","such","only","also","just","so","very","how","what","which","who","when",
           "where","new","old","first","long","great","center","align","class","style",
           "display","position","width","font","color","http","table","return","function",
           "null","left","right","source","height","nbsp","www"},
}

def load_counter(top100k_path):
    counter = Counter()
    with top100k_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\r\n").split("\t", 1)
            if len(parts) != 2: continue
            try: c = int(parts[0])
            except ValueError: continue
            counter[parts[1]] += c
    return counter

def main():
    today = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())

    # ── 第一阶段：收集所有候选 (iso, top100k_path, text_bytes, src) ──
    candidates = []
    wiki_dir = FF / "wikipedia"
    if wiki_dir.is_dir():
        for d in sorted(wiki_dir.iterdir()):
            if not d.is_dir(): continue
            tk, mj = d / "top100k.txt", d / "meta.json"
            if not (tk.exists() and mj.exists()): continue
            m = json.loads(mj.read_text(encoding="utf-8"))
            candidates.append((norm(d.name), tk, m.get("text_bytes", 0), m.get("total_tokens", 0), "wikipedia"))

    for src_name in ("ultrafineweb_l3", "fineweb2_hq_plus"):
        p = FF / src_name
        if not p.is_dir(): continue
        for d in sorted(p.iterdir()):
            if not d.is_dir(): continue
            tk, mj = d / "top100k.txt", d / "meta.json"
            if not (tk.exists() and mj.exists()): continue
            m = json.loads(mj.read_text(encoding="utf-8"))
            candidates.append((norm(d.name), tk, m.get("text_bytes", 0), m.get("total_tokens", 0), src_name))

    # ── 第二阶段：按 (iso, src_type) 合并计数；语言级任一来源 >1 GiB 入选 ──
    from collections import defaultdict
    lang_src_groups = defaultdict(list)  # (iso, src_type) → [(path, tb, tt)]
    for iso, path, tb, tt, src_name in candidates:
        lang_src_groups[(iso, src_name)].append((path, tb, tt))

    eligible_langs = {iso for iso, _ in lang_src_groups}
    print(f"处理语种 (全量, 筛选由下游完成): {len(eligible_langs)}")
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    languages_meta = {}
    total_bytes = 0

    # ── 第三阶段：按语种处理（per-src-type fu，体积加权） ─────────────
    for iso in sorted(eligible_langs, key=str.lower):
        allowed = LANG_SCRIPTS.get(iso, DEFAULT_SCRIPTS)
        keep_diac = iso in KEEP_DIACRITIC_SINGLE

        # 按 src_type 合并：组内 count 相加，tokens 相加，体积相加
        src_types = []  # [(merged_counter, text_bytes_sum, total_tokens_sum, src_type_name)]
        total_tokens_all = 0
        sum_tb_all = 0

        for src_name in ("wikipedia", "ultrafineweb_l3", "fineweb2_hq_plus"):
            entries = lang_src_groups.get((iso, src_name), [])
            if not entries:
                continue
            merged_cc = Counter()
            tb_sum = 0
            tt_sum = 0
            for path, tb, tt in entries:
                raw_counter = load_counter(path)
                for w, c in raw_counter.items():
                    w_clean, reason = clean_one(w, iso, allowed, keep_diac)
                    if reason is None:
                        merged_cc[w_clean] += c
                tb_sum += tb
                tt_sum += tt
            if merged_cc:
                src_types.append((merged_cc, tb_sum, tt_sum, src_name))
                total_tokens_all += tt_sum
                sum_tb_all += tb_sum

        if total_tokens_all <= 0 or not src_types:
            continue

        # 体积加权 fu 合并：word → fu_sum（全局分母）
        #   fu_i(w) = count_i(w) / tokens_i   (组内合并后的 fu)
        #   fu_sum   = Σ_{i∋w} fu_i(w) * V_i
        #   fu_final = fu_sum / Σ_all V_i     （分母=该语种全部来源体积之和，
        #                                       词在某来源缺席按 0 频计）
        #   不得按"出现过该词的来源"逐词归一：小来源独有词会逃过大体积稀释，
        #   词频虚高（如 bew 的 wiki 独有词 ~57 倍），Σfu 可 >1，band-sum 估计 >100%
        word_fu_weight = {}
        vol_total = 0.0
        for cc, tb_sum, tt_sum, src_name in src_types:
            if tt_sum <= 0 or tb_sum <= 0:
                continue
            vol_total += tb_sum
            inv_tt = 1.0 / tt_sum
            for w, c in cc.items():
                fu_i = c * inv_tt
                if w in word_fu_weight:
                    word_fu_weight[w] += fu_i * tb_sum
                else:
                    word_fu_weight[w] = fu_i * tb_sum

        if vol_total <= 0:
            continue

        # 分 cB 带（双门槛）
        bands = [[] for _ in range(N_BANDS)]
        add_space = 1 if iso in SPACE_WORD_LANGS else 0
        kept_set = set()

        for w, fu_sum in word_fu_weight.items():
            fu_w = fu_sum / vol_total
            if fu_w <= 1e-6:
                continue
            word_bytes = len(w.encode("utf-8")) + add_space
            if fu_w / word_bytes <= FREQ_CUT:
                continue
            cb = int(round(-100 * math.log10(fu_w)))
            if cb < 0:
                cb = 0
            if cb >= N_BANDS:
                cb = N_BANDS - 1
            bands[cb].append(w)
            kept_set.add(w)

        # 覆盖率：kept_set 内各组合并 count 合计 / total_tokens_all
        kept_count_total = 0
        for cc, _, _, _ in src_types:
            for w in kept_set:
                kept_count_total += cc.get(w, 0)
        coverage_real = kept_count_total / total_tokens_all if total_tokens_all > 0 else 0.0
        written = sum(len(b) for b in bands)

        src_names = sorted(st[3] for st in src_types)
        header = {"format": "cB", "version": 1, "lang": iso, "sources": src_names}
        payload = msgpack.packb([header] + bands, use_bin_type=True)
        out_bytes = gzip.compress(payload, compresslevel=9)
        outfile = OUT_DATA / f"small_{iso}.msgpack.gz"
        outfile.write_bytes(out_bytes)
        total_bytes += len(out_bytes)

        languages_meta[iso] = {
            "kept": written,
            "coverage": round(coverage_real, 6),
            "sources": {
                FULL_SRC[sn]: {"text_bytes": tb_sum, "tokens": tt_sum}
                for _, tb_sum, tt_sum, sn in src_types
            },
        }
        src_info = "; ".join(f"{FULL_SRC[sn]}={tb_sum/ONE_GIB:.2f}G" for _, tb_sum, _, sn in src_types)
        print(f"  {iso:<12} kept={written:>7} cov={coverage_real*100:>5.1f}% {src_info}")

    OUT_BASE.mkdir(parents=True, exist_ok=True)
    out_meta = {
        "version": 6,
        "generatedAt": today,
        "description": (
            "pyicu BreakIterator corpus (wiki + ultra + fw2), self-built cB band. "
            "All-script unicode rule set. "
            "Word gate: fu_w > 1e-6 AND fu_w/word_bytes > 2e-7. "
            "No eligibility filter applied here; downstream tiers select by "
            "per-language total source text_bytes (see sources)."
        ),
        "languages": languages_meta,
    }
    mpath = OUT_BASE / "meta.json"
    mpath.write_text(json.dumps(out_meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"\n{len(languages_meta)} langs, {total_bytes/1024/1024:.1f} MB")
    print(f"meta.json -> {mpath}")

if __name__ == "__main__":
    main()
