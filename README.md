# 社區每日盯盤

每天台灣時間 **17:00**，Cursor Automation 會抓：

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
- 報告備份在 `reports/`，並回覆到 Issue「社區每日盯盤」

## 每日寄信

由 [Cursor Automation](https://cursor.com/automations) 在台灣時間 17:00 跑 `python3 watch/daily_report.py --send-email --commit`，寄到 `cequ3108@gmail.com`。

GitHub Action「社區每日盯盤」只留手動 **Run workflow** 當備援，不再每天自動跑。

## 本地

```bash
python3 -m unittest discover -s tests -v
python3 watch/daily_report.py --send-email
```

估價帶在 `watch/communities.json`。
