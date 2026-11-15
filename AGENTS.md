# 專案協作規則

## 多主機開發與 GitHub 同步

- 本專案會在不同主機上開發，GitHub 是各主機交換已完成工作的共同來源。
- 開始工作前，先檢查目前分支與未提交變更，並 fetch 遠端最新狀態。安全時以 fast-forward 同步目前分支；保留使用者既有的本機變更。
- 每個獨立開發任務優先使用 `codex/` 開頭的任務分支。切換主機接續同一任務時，先在原主機 push，再到接手主機同步該分支。
- 每次完成修改並通過適當檢查後，必須 commit 並 push 到 `origin`，包括文件與這份協作規則的修改。不要只把完成的工作留在本機。
- 只提交本次任務的變更；`settings.json` 等使用者原有的未提交設定應保留，避免混入其他任務或上傳帳密、Cookie、登入憑證。
- 遇到衝突或遠端更新時，保留雙方工作並處理同步問題；不要 force-push、重設或覆寫其他主機的提交。
- 回報完成時說明分支、commit 與 push 結果。若無法 push，清楚說明原因與尚未同步的內容。

## Windows CMD：首次安裝與啟動

以下適用於乾淨的 Windows 10／11 環境，將最新版 `main` 的 ZIP 解壓縮至
`D:\my-ticket-bot` 後，使用 **Windows 命令提示字元（CMD）** 執行。
使用 ZIP 不需要安裝 Git、VS Code 或 PowerShell。

### 1. 準備 Python 與 Chrome

- 安裝 **Python 3.12 64 位元**；例如使用官方 Python 3.12.10 Windows installer（64-bit）。
  安裝時勾選 `Add python.exe to PATH`，保留 pip、Tcl/Tk 與 Python Launcher。
- 安裝 Google Chrome。
- 安裝完成後重新開啟 CMD，讓新的環境變數生效。
- 確認 `D:\my-ticket-bot` 下直接有 `settings.py`、`chrome_tixcraft.py` 與
  `pip-req.txt`，而不是多包一層 `my-ticket-bot-main` 資料夾。
- 首次安裝套件與取得驅動需要網路連線。

### 2. 建立 Python 環境並安裝套件

逐行執行：

```cmd
cd /d D:\my-ticket-bot
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.venv\Scripts\python.exe -m pip install -r pip-req.txt requests
```

`cd /d` 會同時切換磁碟與資料夾。後續直接指定 `.venv` 的 Python，
不需要另外啟用虛擬環境，也不要使用其他主機複製來的 `.venv`。

### 3. ChromeDriver

首次執行由 Selenium Manager 自動取得相容的 ChromeDriver，之後可以使用快取，
不需要手動下載或複製到 `webdriver`。Manager 成功後不再執行舊版下載器；
Manager 失敗時，才嘗試專案中既有的本機驅動。

版本查詢與下載的單次網路請求預設最多等待 10 秒。網路較慢、首次下載需要
更長時間時，可在同一個 CMD 視窗先執行 `set SE_TIMEOUT=60`，再開啟 GUI。
這是單次請求的逾時值，不是整個瀏覽器啟動的總時間上限。

### 4. 開啟設定介面

```cmd
.venv\Scripts\python.exe settings.py
```

設定購票網址、票數與票區；瀏覽器選 `Chrome`，引擎選 `Selenium`。
需要自動按下一步時啟用「掛機模式」，按「存檔」後再按「執行」。
目前遠大自動流程會到「付款結帳」頁停止，不會自動按「前往付款」。
GUI 會顯示啟動中、已啟動或失敗，以及本機日誌路徑；啟動期間請勿重複點擊。
日誌會遮蔽設定中的帳密與憑證，不要將使用者設定或原始截圖加入提交。
遠大自動重整至少間隔 1 秒；設定較長間隔時仍使用較長值。

### 日後啟動

第一次安裝完成後，每次只需要：

```cmd
cd /d D:\my-ticket-bot
.venv\Scripts\python.exe settings.py
```
