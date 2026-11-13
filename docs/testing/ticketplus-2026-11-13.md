# 遠大售票複測：2026-11-13

## 結論

不能判定遠大完整自動購票正常。`main` 尚未包含 11/8 的遠大修正，
實站仍無法自動選場；11/8 任務分支通過全部 47 項既有離線測試，
本次使用者手動登入後，實站已完成自動選場、進入選票頁與填入一般全票 1 張。
這只驗證前端選票操作，尚未驗證服務端配票或保留庫存。
確認頁與付款方式頁的完整自動流程仍未完成。

本輪沒有修改正式購票程式，也沒有送出訂單或付款。

## 版本與環境

- 儲存庫：`https://github.com/Boazzzzz/my-ticket-bot.git`。
- clone 當下遠端預設分支是 `feature/my-ticket-bot`（`f9a4f04`），不是 `main`。
- `origin/main`：`bb1c2e7dd1f49b8f7758fa46a669a9f346f17070`。
- 11/8 修正版：`origin/codex/ticketplus-functional-test`，
  `8806e2c8dd1891524976aa6e256d232ac8b04a28`。
- 複測分支：`codex/ticketplus-retest-20261113`，以 11/8 修正版為基礎。
- Windows 11、Python 3.12.16、Selenium 4.52.0、Chrome 157.0.8103.39、
  ChromeDriver 157.0.8103.78。
- 原主機沒有可用的 Python；下載的執行環境放在 `.tools/` 與 `.venv/`，不提交。
- 原有 `settings.json` 未修改；實站工具使用暫存設定清空帳密、停用 OCR 與自動送出，
  張數設為 1。沒有讀出或輸出帳密、Cookie。

## 離線回歸與 main 對照

| 載入的正式程式 | 通過 | 失敗 | 錯誤 | 總數 |
| --- | ---: | ---: | ---: | ---: |
| 11/8 修正版 `8806e2c` | 47 | 0 | 0 | 47 |
| main `bb1c2e7` | 34 | 12 | 1 | 47 |

使用相同的 11/8 測試資料與測試程式；main 對照只將匯入的 `chrome_tixcraft`
換成 `git show origin/main:chrome_tixcraft.py` 取得的原始碼，不改本機正式檔案。
47 項中，30 項是正式選場／選票的瀏覽器 DOM 測試，17 項是任務分支診斷工具的
保護測試；後者並非 main 已有完整結帳功能的證據。

main 失敗包含新版場次包裝結構、日期篩選、指定票種失敗後誤用全頁備援、
無驗證碼的下一步、兩種頁尾、按鈕狀態更新及 OCR 提交結果回傳。
元素查詢例外時另重現 `UnboundLocalError: area_list_count`。

修正版的離線測試命令：

```powershell
$env:SE_CACHE_PATH = "$PWD\.tools\selenium"
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

通過只代表測試涵蓋的本機 DOM／模擬情境；OCR 分支使用模擬回傳結果，
不代表實站驗證碼辨識與服務端驗證通過。

## 本次實站結果

活動沿用 11/8 紀錄的 VERA《NEXTERA》：
`https://ticketplus.com.tw/activity/146cbb24e0128239e2c80db2c63fa417`。

同一公開活動頁本次觀察：

- 舊選取器 `div#buyTicket > div.sesstion-item > div.row`：0 筆。
- 修正版 `div#buyTicket div.sesstion-item > div.row`：1 筆。
- 呼叫 main 的正式選場函式：回傳 `false`，仍留在活動頁。
- 修正版第一次安全測試：`date_selected: true`，接著顯示登入表單，
  結果為 `needs_manual_login`。
- 加上登入等待後，使用者完成手動登入，原流程自動繼續，進入選票頁。
- 正式選票函式選到「霓虹迷宮」全票 NT$3,080，實際票種容器的張數為 1；
  測試結果為 `quantity_selected`，程序以 0 結束。截圖亦確認相同票區、金額及張數。
- 展開票區時發生 `ElementClickInterceptedException`，正式程式既有的 JavaScript
  點擊備援成功展開，後續完成張數設定；本次沒有改寫點擊邏輯。
- 本次未設定票價／票區關鍵字；因此不能據此驗收指定 NT$2,480 票區或價格篩選。
- 選票後截圖同時顯示該票區「剩餘 0」。選票前的就緒檢查截圖仍在載入中，
  無法確認選票前的即時餘量，也無法判定這個數字是否扣除了目前選取張數。
  未呼叫下一步驗證配票，因此只能確認前端顯示一張，不能宣稱已取得或保留票券。
- 本輪實站沒有測試無驗證碼下一步、OCR、確認座位或結帳。

測試命令：

```powershell
.\.venv\Scripts\python.exe tools/ticketplus_smoke_test.py --url https://ticketplus.com.tw/activity/146cbb24e0128239e2c80db2c63fa417
```

實際完成選票的命令另加 `--login-wait-seconds 900`，讓使用者手動登入。
本輪完成後的結果摘要如下：

```json
{
  "status": "quantity_selected",
  "date_selected": true,
  "date_selector_count": 1,
  "order_page_reached": true,
  "ticket_number_assigned": true,
  "selected_ticket": {
    "ticket_type": "霓虹迷宮／全票／NT$3,080",
    "quantity": 1
  },
  "captcha_tested": false,
  "order_submitted": false
}
```

摘要將原始票種文字整理為易讀格式；原始結果另包含「剩餘 0」。
此工具的成功條件是一般票種容器的前端張數為 1，不包含庫存或配票驗證。
成功後已自動關閉這次測試 Chrome，沒有繼續按下一步、送單或付款。

## 額外確認的問題與限制

### 沒有本機驅動時，啟動器仍可能中斷

第一次執行實站工具時，`webdriver/chromedriver.exe` 不存在，
`load_chromdriver_normal()` 在呼叫 Selenium Manager 後仍執行
`chromedriver_autoinstaller_max.install()`。此機環境的舊下載器在
`chromedriver_version >= "115"` 處因版本為 `None` 拋出 `TypeError`。

以本機 mock 讓 `webdriver.Chrome()` 成功回傳，再讓舊下載器拋錯，
確認啟動器仍會向外拋出該錯誤；成功啟動 Selenium Manager 並不能避免這條路徑。
此問題也可能讓已啟動的瀏覽器沒有被回傳及正常清理。

本輪將 Selenium 回歸測試已使用的相容驅動複製到專案既有的
`webdriver/chromedriver.exe` 位置後，實站測試才順利進行；這是本機環境處理，
沒有修復啟動器程式，驅動二進位也不提交。

### 選票後自動前進有設定條件

儲存庫設定為 Selenium、2 張、`ocr_captcha.force_submit: false`。
11/8 的無驗證碼自動下一步需啟用 GUI「掛機模式」並存檔、重啟機器人；
手動模式保留人工按下一步。不能將此預期行為誤判為 11/8 修正失效。
本輪未更動使用者設定，也未使用 2 張票的設定操作實站。

### 完整自動結帳仍有缺口

- 本機 HTML 呼叫正式 `ticketplus_confirm()`，結果仍為
  `terms_checked: true`、`next_button_click_count: 0`，重現 11/8 紀錄的中斷點。
- `ticketplus_main()` 仍沒有 `/checkout/` 付款方式頁的處理流程。
- nodriver 的遠大選場與選票流程仍有未完成註解，不能視為已驗收替代方案。
- 11/8 的人工逐步建立待付款訂單不等於正式 GUI 全自動流程成功。

## 證據與下一步

離線測試 log、main 對照用原始碼與執行腳本、公開頁面選取器觀察、
本機缺口觀察均保存在本機 `.tools/`；實站工具截圖與結果保存在其輸出的系統暫存目錄。
不提交會員資料、實站截圖、Cookie、帳密或訂單資訊。

若要使用 11/8 修正，需先使用包含 `8806e2c` 的分支；目前不能只 clone main 後
就期待這些修正存在。後續應修復啟動器的多餘舊下載路徑，並另行驗證指定票種、
即時庫存、下一步配票與 OCR，再實作、驗證確認頁與付款方式頁。
這份報告沒有把這些未完成項目標為通過。
