# 遠雄北府苑每日盯盤

每天台灣時間 **17:00**，GitHub Action 會抓 [591 遠雄北府苑在售](https://market.591.com.tw/102191/sale)，合併同一戶的重複刊登，然後算出開價、便宜價、合理價、平價。

報告分兩塊：

1. **有沒有掉入合理價**（開價 ≤ 合理價）
2. **完整表格**：開價／便宜價／合理價／平價、超出合理、是否降過價

## 你會怎麼收到

Action 會把報告回覆到 Issue「遠雄北府苑｜每日盯盤」。

請先：

1. 進 GitHub → **Actions**，若被關掉請打開
2. 合併這份 workflow 到 `master`
3. 第一次跑完後打開該 Issue，按 **Subscribe**／Watch（或 Watch 整個 repo）
4. GitHub 就會在每天傍晚把同一封報告寄到你的信箱

也可在 Actions 頁按 **Run workflow** 手動跑一次。

## 本地預覽

```bash
python3 -m unittest discover -s tests -v
python3 watch/daily_report.py
```

用固定樣本、不打 591：

```bash
python3 watch/daily_report.py --fixture tests/fixtures/sale_list_sample.json
```

估價帶與指定戶在 `watch/communities.json`。之後要加社區，把 591 社區網址與格局／預算補進這個檔即可。
