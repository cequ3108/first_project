# 社區每日盯盤

每天台灣時間 **17:00**，GitHub Action 會抓：

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

## 你要開的設定（Gmail Secret）

1. 打開這個頁面：https://github.com/cequ3108/first_project/settings/secrets/actions
2. 按 **New repository secret**
3. Name 填：`GMAIL_APP_PASSWORD`
4. Secret 填 Gmail「應用程式密碼」（16 碼，不是登入密碼）
5. 按 **Add secret**

Gmail 應用程式密碼在這裡產生：https://myaccount.google.com/apppasswords  
（帳號要先開兩步驟驗證，選「郵件」即可。）

設好後可到 https://github.com/cequ3108/first_project/actions/workflows/daily-watch.yml 按 **Run workflow** 先試一次。之後每天 17:00 會自動跑。

GitHub 的雲端 IP 有時會被 591 擋；Action 會用 Chrome 指紋抓資料。若仍失敗，日誌會寫 `591 抓取失敗`。

## 本地

```bash
python3 -m unittest discover -s tests -v
python3 watch/daily_report.py --send-email
```

估價帶在 `watch/communities.json`。
