# 社區每日盯盤

每天台灣時間 **17:00**，Cursor 會直連 591 抓：

- [遠雄北府苑](https://market.591.com.tw/102191/sale)
- [西門大院](https://market.591.com.tw/3681545/sale)
- [遠雄新源邸](https://market.591.com.tw/39785/sale)
- [國泰文海硯](https://market.591.com.tw/39711/sale)
- [國泰文林硯](https://market.591.com.tw/39784/sale)
- [國泰磐耘](https://market.591.com.tw/5892392/sale)
- [允將海安](https://market.591.com.tw/3694974/sale)
- [藏美表參道](https://market.591.com.tw/5885447/sale)
- [遠雄頂美](https://market.591.com.tw/101914/sale)
- [富立真邦](https://market.591.com.tw/39226/sale)
- [富立和築](https://market.591.com.tw/39225/sale)

合併同一戶的重複刊登，算出開價、便宜價、合理價、平價，並把當天開價寫進 GitHub，隔天才能對出「有沒有降價」。

## 報告長這樣

1. **有沒有掉入合理價**（開價 ≤ 合理價）
2. **今日降價**（591 已降，或比 GitHub 上次紀錄更低）
3. **各社區完整表**

每天會：

- 寄信到 `cequ3108@gmail.com`
- 把價格寫進 `data/daily/YYYY-MM-DD.json` 與 `data/price-history.json`
- 報告備份在 `reports/`

## 為什麼不用 GitHub Action 排程

GitHub 託管 runner 的雲端 IP 會被 591/CloudFront 直接擋下（HTTP 403），連 Chrome TLS 與 `r.jina.ai` 代抓也會被 Cloudflare 挑戰頁擋。Gmail Secret 沒問題，問題在抓資料。

因此：

- **每日 17:00 寄信：Cursor**（這個環境可以直連 591）
- GitHub Action 只保留手動 `workflow_dispatch`，方便之後若改用**自家 IP 的 self-hosted runner** 再打開排程

較耐久的做法：到 https://cursor.com/automations/new 建一則 Automation（repo `cequ3108/first_project`，branch `master`，cron 若用 UTC 填 `0 9 * * *`）。對話裡的 timer 大約一週會過期。

## 本地

```bash
python3 -m unittest discover -s tests -v
python3 watch/daily_report.py --send-email
```

估價帶在 `watch/communities.json`。已成交戶用社區的 `exclude` 過濾（例如西門大院 17F / 31.7 坪）。
