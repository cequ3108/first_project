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
- 報告備份在 `reports/`，並 **push 回 `master`**（下次 Cursor 才讀得到昨天的開價）

## 手機 Cursor：自動寄信 + 資料怎麼放

Cursor 雲端每次都是**新的一台機器**，沒有獨立檔案櫃。你在手機上編輯的程式、社區、開價紀錄，真正能留下來的地方是 GitHub 這個 repo。正確分工是：

| 放哪 | 放什麼 | 不要放什麼 |
|---|---|---|
| **Cursor Secrets** | `GMAIL_APP_PASSWORD` | 程式、開價 JSON |
| **GitHub repo（`master`）** | 程式、`watch/communities.json`、`data/`、`reports/` | Gmail 密碼 |
| **Cursor Automation** | 每天 17:00 要跑的指令 | 不要選「No repository」 |

中間會失敗，通常是這三種：

1. Secret 只在 GitHub、Automation 卻在 Cursor 跑 → 抓得到 591 但寄不出信
2. Automation 沒選 repo、或選錯分支 → 讀不到 `data/price-history.json`
3. 跑完有寫檔但沒 push 回 `master` → 隔天又是空的昨天

### 1. 密碼只放 Cursor（手機 Safari 即可）

1. 打開 https://cursor.com/dashboard/cloud-agents
2. 進 **Secrets**
3. 新增：
   - `GMAIL_APP_PASSWORD`：Gmail 應用程式密碼（16 碼，不是登入密碼）
   - 可選 `MAIL_TO` / `MAIL_FROM`：`cequ3108@gmail.com`（沒設也沒關係，程式會讀 `watch/communities.json` 的 `mail_to`）
4. **GitHub Action 的 Secret 可以不用再管**（GitHub 雲端 IP 抓不到 591，排程已關掉）

Gmail 應用程式密碼：https://myaccount.google.com/apppasswords

### 2. 建每日 Automation（不要用對話 timer）

對話裡的 timer 大約一週會過期。請用手機打開 https://cursor.com/automations/new ：

1. Trigger：Scheduled / cron
2. Cron（UTC）：`0 9 * * *`（= 台灣 17:00）
3. **一定要選 repository**：`cequ3108/first_project`，branch **`master`**
   - 預設常是 No repository，那樣沒有檔案，一定失敗
4. 提示貼這段：

```
每天台灣時間 17:00：在 master 跑社區每日盯盤並寄信。

1. git fetch origin master && git checkout master && git pull origin master
2. python3 watch/daily_report.py --send-email --commit --push
3. 用繁體中文簡短回覆：寄到哪、幾個社區、有沒有掉入合理價／今日降價
4. 不要印出 GMAIL_APP_PASSWORD 或任何密鑰
5. 遵守 watch/communities.json 的 exclude（已成交戶不要列入）
6. 不要重新打開 GitHub 託管 runner 的 cron；GitHub 雲端 IP 抓不到 591
7. 開價 JSON 必須 push 回 master，不要只開 PR 就把資料留在別的分支
```

### 3. 你在手機改社區、估價帶

用 Cursor 改 `watch/communities.json` 後，**合併進 `master`**。Automation 只讀 `master`，開在別的對話分支的修改，隔天不會生效。

## 為什麼不用 GitHub Action 排程

GitHub 託管 runner 的雲端 IP 會被 591/CloudFront 直接擋下（HTTP 403），連 Chrome TLS 與 `r.jina.ai` 代抓也會被 Cloudflare 挑戰頁擋。

因此：

- **每日 17:00 寄信：Cursor Automation**（可以直連 591，密碼用 Cursor Secrets）
- GitHub 只當硬碟，Action 只保留手動 `workflow_dispatch`

## 本地 / 手動試一次

```bash
python3 -m unittest discover -s tests -v
python3 watch/daily_report.py --send-email --commit --push
```

估價帶在 `watch/communities.json`。已成交戶用社區的 `exclude` 過濾（例如西門大院 17F / 31.7 坪）。
