# 遠大售票功能測試：2026-11-08

## 結論

目前 Selenium 版本的遠大自動選場失敗，尚不能認定完整購票流程正常。
nodriver 版本的遠大選場、選票及驗證碼流程仍有 TODO，不能當作已完成的替代方案。

## 測試環境與範圍

- Python 3.13.15、macOS arm64，使用專案 `.venv` 中的 Selenium。
- 活動：2026 VERA 四周年演唱會《NEXTERA》，2026-12-27 18:00，Clapper Studio。
- 公開活動頁：https://ticketplus.com.tw/activity/146cbb24e0128239e2c80db2c63fa417
- 手動瀏覽時，活動頁顯示「立即購買」。這是測試當時狀態，之後可能改變。
- 測試使用一張票的暫存設定，清空帳密及登入憑證；原有 `settings.json` 未更動。
- 呼叫專案現有的 `ticketplus_date_auto_select()`；未接受條款、未解驗證碼、未送出訂單、未付款。
- 截圖及執行紀錄留在本機暫存目錄，沒有上傳帳密、Cookie 或個人資料。

## 已確認的失敗原因

`chrome_tixcraft.py` 的 `ticketplus_date_auto_select()` 使用：

```css
div#buyTicket > div.sesstion-item > div.row
```

新版活動頁在 `#buyTicket` 與 `.sesstion-item` 之間增加了一層 `div`。
在同一活動頁實測，舊選取器匹配 0 筆；下列放寬祖先關係的選取器匹配 1 筆：

```css
div#buyTicket div.sesstion-item > div.row
```

實際執行舊選場函式，連續三次皆未找到場次，測試以
`activity_selectors_not_found` 結束。這次只記錄測試及原因，未修改正式購票邏輯。

## 尚未驗證

- 遠大帳號登入與登入後導向。
- 自動選票區、填張數與事件專屬問答。
- 圖片驗證碼辨識與服務端驗證。
- 訂單、座位保留及付款流程。

## 在其他主機重跑

先同步任務分支並準備專案 Python 依賴，選擇當下仍可購票的公開活動頁：

```sh
python tools/ticketplus_smoke_test.py --url https://ticketplus.com.tw/activity/EVENT_ID
```

如需讓使用者在測試 Chrome 視窗手動登入，可加上
`--login-wait-seconds 900`，最多等待 15 分鐘。腳本不會自動輸入帳密，
也不會解驗證碼、接受條款或送出訂單。正常填入一張票時回傳 0；
登入待處理、逾時或選場／選票失敗時回傳非 0。
