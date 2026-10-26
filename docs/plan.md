# 语料抽样下载计划（行动方案）

## 入选条件（文本体积）

每个入选语种须同时满足：
1. **Wikipedia 本地**：parquet 解压后纯文本 ≥ 1 GiB
2. **Web 通道（fw2 或 ultra）**：parquet 解压后纯文本 ≥ 1 GiB

## 下载源与压缩比

| 源 | 列名 | 压缩比（压缩:文本） | 入选阈值（压缩 MiB） | 访问端点 |
|----|------|---------------------|----------------------|----------|
| Wikipedia | text | ~1:1 | ≥ 1000 MB | 本地 `F:\data\corpus\wikipedia-monthly\20261001\{iso2}\train\` |
| FineWeb2 | text | ~4.3:1 | ≥ 233 MB | ModelScope / HF |
| Ultra-L3 | content | ~4.5:1 | ≥ 223 MB | ModelScope |

## 第一批：wiki + web 双通道均可达（按 resource.md 数据）

下表中"web 源"优先取 fw2；fw2 无数据则取 ultra（仅 eng 有 ultra）

| # | 语种 | wiki(GiB) | web源 | web(压缩MiB) | 状态 |
|---|------|-----------|-------|--------------|------|
| 1 | eng | wiki≥1 ✓ | ultra | 861070 ✓ | 待下载 |
| 2 | rus | ≥1 ✓ | fw2 (HF) | 311570 ✓ | 待 |
| 3 | spa | ≥1 ✓ | fw2 (HF) | 122787 ✓ | 待 |
| 4 | deu | ≥1 ✓ | fw2 | 135954 ✓ | 待 |
| 5 | cmn | ≥1 ✓ | fw2 | 178741 ✓ | 待 |
| 6 | fra | ≥1 ✓ | fw2 | 100729 ✓ | 待 |
| 7 | ita | ≥1 ✓ | fw2 | 62017 ✓ | 待 |
| 8 | jpn | ≥1 ✓ | fw2 (HF) | 98274 ✓ | 待 |
| 9 | por | ≥1 ✓ | fw2 (HF) | 51680 ✓ | 待 |
| 10 | pol | ≥1 ✓ | fw2 (HF) | 40106 ✓ | 待 |
| 11 | tur | wiki<1 ✗ → 实际需验算 | fw2 (HF) | 22124 | 边缘 |
| 12 | arb | ≥1 ✓ | fw2 | 18876 ✓ | 待 |
| 13 | nld | ≥1 ✓ | fw2 (HF) | 34343 ✓ | 待 |
| 14 | ell | wiki<1 (785MB) ✗ | fw2 | 17704 | **仅 web 通道,不入选** |
| 15 | ron | wiki<1 (404MB) ✗ | fw2 | 18588 | 不入选 |
| 16 | ukr | ≥1 ✓ | fw2 (HF) | 17112 ✓ | 待 |
| 17 | ind | wiki<1 (848MB) ✗ | fw2 | 23672 | 不入选 |
| 18 | fas | wiki<1 (997MB) ✗ → 接近阈值 | fw2 | 17342 | **边缘待实测** |
| 19 | hin | wiki<1 (271MB) ✗ | fw2 | 7062 | 不入选 |
| 20 | ces | ≥1 ✓ | fw2 | 21365 ✓ | 待 |
| 21 | hun | ≥1 ✓ | fw2 | 18163 ✓ | 待 |
| 22 | kor | ≥1 ✓ | fw2 (HF) | 17575 ✓ | 待 |
| 23 | vie | wiki<1 (879MB) ✗ | fw2 | 16816 | 不入选 |
| 24 | swe | ≥1 ✓ | fw2 (HF) | 15142 ✓ | 待 |
| 25 | dan | wiki<1 (370MB) ✗ | fw2 | 13567 | 不入选 |
| 26 | fin | wiki<1 (796MB) ✗ | fw2 | 11115 | 不入选 |
| 27 | nob | wiki<1 (672MB) ✗ | fw2 | 10772 | 不入选 |
| 28 | tha | wiki<1 (441MB) ✗ | fw2 | 10884 | 不入选 |
| 29 | slk | wiki<1 (284MB) ✗ | fw2 | 10323 | 不入选 |
| 30 | bul | wiki<1 (578MB) ✗ | fw2 | 10351 | 不入选 |
| 31 | ben | wiki<1 (546MB) ✗ | fw2 | 5630 | 不入选 |
| 32 | bos | wiki=0 ✗ | fw2 | 5627 | 不入选 |
| 33 | lit | wiki<1 ✗ | fw2 | 5470 | 不入选 |
| 34 | cat | ≥1 ✓ | fw2 | 4270 ✓ | 待 |
| 35 | heb | ≥1 ✓ | fw2 | 4424 ✓ | 待 |
| 36 | hrv | wiki<1 (309MB) ✗ | fw2 | 3032 | 不入选 |
| 37 | ekk | wiki<1 (308MB) ✗ | fw2 | 3696 | 不入选 |
| 38 | slv | wiki<1 (336MB) ✗ | fw2 | 4867 | 不入选 |
| 39 | lvs | wiki<1 (164MB) ✗ | fw2 | 3096 | 不入选 |
| 40 | urd | wiki<1 (267MB) ✗ | fw2 | 1434 | 不入选 |
| 41 | als | wiki=0 ✗ | fw2 | 2423 | 不入选 |
| 42 | azj | wiki<1 (282MB) ✗ | fw2 | 2488 | 不入选 |
| 43 | zsm | wiki<1 (291MB) ✗ | fw2 | 3024 | 不入选 |
| 44 | mar | wiki<1 (104MB) ✗ | fw2 | 1303 | 不入选 |
| 45 | srp | ≥1 ✓ | fw2 (HF) | 1501 ✓ | 待 |
| 46 | kan | wiki<1 (171MB) ✗ | fw2 | 816 | 不入选 |
| 47 | tam | wiki<1 (319MB) ✗ | fw2 | 2062 | 不入选 |
| 48 | npi | wiki<1 (45MB) ✗ | fw2 | 1742 | 不入选 |
| 49 | kat | wiki<1 (308MB) ✗ | fw2 | 1287 | 不入选 |
| 50 | mkd | wiki=0 ✗ | fw2 | 1110 | 不入选 |
| 51 | ary | wiki=0 ✗ | fw2 | 568 | 不入选 |
| 52 | kaz | wiki<1 (208MB) ✗ | fw2 | 1338 | 不入选 |
| 53 | mal | wiki<1 (201MB) ✗ | fw2 | 1260 | 不入选 |
| 54 | hye | wiki<1 (692MB) ✗ | fw2 | 531 | 不入选 |

## 入选按优先级分批

### A 组：双通道均 ≥ 1GB 文本（ModelScope 可下载 fw2）
deu, fra, ita, arb, ces, hun, cat, heb (8 语种)
- web 端每语种下载 fw2 parquet 约 4 GB compr → 截断至 1 GiB 文本停止
- 总下载量估算：~32 GB

### B 组：双通道均 ≥ 1GB 文本（HF 回退，因 ModelScope 无此语种 fw2）
rus, spa, jpn, por, pol, nld, ukr, kor, swe, srp (10 语种)
- 需从 hf-mirror 访问 fw2
- 总下载量估算：~40 GB

### C 组：仅靠 ultra（ModelScope）
eng（web=ultra_l3）(1 语种)
- 下载 ultra parquet ~4.5 GB compr → 截断至 1 GiB 文本
- 下载量：~4.5 GB

### 未定：边缘语种
- fas (wiki=997MB，接近阈值，需实测)
- tur (wiki=708MB，需实测)

## 数据已下载现状（此前 session 遗留）

位置 `F:\data\WordFrequency\{source}\{lang}\part-00000.txt`

| 源 | 语种 | 大小 |
|----|------|------|
| ultra_l3 | en | 1.00 GiB (ultra 列名=content,到达 ✓) |
| fineweb2_hq | rus | 1.00 GiB (需 hf-mirror 但用 ModelScope 取下) |
| fineweb2_hq | spa | 1.00 GiB (同) |
| wikipedia | eng_Latn | 1.01 GiB ✓ |
| wikipedia | rus_Cyrl | 1.00 GiB ✓ |
| wikipedia | spa_Latn | 1.01 GiB ✓ |
| wikipedia | ar | 1.01 GiB |
| wikipedia | en | 1.01 GiB |
| wikipedia | ja | 1.01 GiB |
| fine_news | eng_Latn | 1.01 GiB (news 已废弃，仅记录) |
| fine_news | rus_Cyrl | 1.00 GiB (同) |
| fine_news | fra_Latn | 0.13 GiB |
| fine_news | jpn_Jpan | 0.18 GiB |
| fine_news | deu_Latn | 0.31 GiB |
| fine_news | cmn_Hani | 0.57 GiB |

## 已下载但"来源不在当前计划"的语种

- fine_news/{eng,rus,fra,jpn,deu,cmn}: fine-news 已废弃，可保留供参考但**不进入后续 pyicu 统计**

## 当前状态总结

- **已达标 (wiki+web 各 1GiB)**: eng, rus, spa — 3 语种
- **部分完成 (wiki 有, web 无)**: eng_Latn(ultra 有), rus_Cyrl(fw2 有), spa_Latn(fw2 有), ja(wiki 有), ar(wiki 有), en(wiki 有)
- **待完成**: deu/fra/ita/arb/ces/hun/cat/heb/jpn/por/pol/nld/ukr/kor/swe/srp — 17 语种 web 通道待下载
- **待实测**: fas, tur
