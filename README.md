# 社區每日盯盤

每天台灣時間 **17:00**，GitHub Action 會抓：

- [遠雄北府苑](https://market.591.com.tw/102191/sale)
- [西門大院](https://market.591.com.tw/3681545/sale)
- [遠雄新源邸](https://market.591.com.tw/39785/sale)
- [國泰文海硯](https://market.591.com.tw/39711/sale)

合併同一戶的重複刊登，算出開價、便宜價、合理價、平價，並把當天開價寫進 GitHub，隔天才能對出「有沒有降價」。

## 報告長這樣

1. **有沒有掉入合理價**（開價 ≤ 合理價）
2. **今日降價**（591 已降，或比 GitHub 上次紀錄更低）
3. **各社區完整表**

每天會：

- 寄信到 `cequ3108@gmail.com`
- 把價格寫進 `data/daily/YYYY-MM-DD.json` 與 `data/price-history.json`
- 報告備份在 `reports/`，並回覆到 Issue「社區每日盯盤」

## 你要開的設定

1. 打開 repo 的 **Actions**
2. 在 GitHub → Settings → Secrets and variables → Actions，新增 `GMAIL_APP_PASSWORD`（Gmail 應用程式密碼）
3. 合併 workflow 到 `master` 後，可按 **Run workflow** 先跑一次

## 本地

```bash
python3 -m unittest discover -s tests -v
python3 watch/daily_report.py --send-email
```

估價帶在 `watch/communities.json`。
