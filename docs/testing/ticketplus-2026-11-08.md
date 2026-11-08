# 遠大售票功能測試：2026-11-08

## 結論

Selenium 版本原本的自動選場失敗已修正。本次實測已完成驗收：自動選場、
使用者手動登入後進入選票頁、自動選擇「夢境邊界」全票 NT$2,480 並填入 1 張。
測試在選票頁停止，沒有按「下一步」、解驗證碼、接受購票條款、送出訂單或付款。
此結果只涵蓋本活動的一般票選票流程，不能推論完整購票與付款流程皆已通過。
nodriver 版本的遠大選場、選票及驗證碼流程仍有 TODO，不能當作已完成的替代方案。

## 測試環境與範圍

- Python 3.13.15、macOS arm64，使用專案 `.venv` 中的 Selenium。
- 活動：2026 VERA 四周年演唱會《NEXTERA》，2026-12-27 18:00，Clapper Studio。
- 公開活動頁：https://ticketplus.com.tw/activity/146cbb24e0128239e2c80db2c63fa417
- 手動瀏覽時，活動頁顯示「立即購買」。這是測試當時狀態，之後可能改變。
- 測試使用一張票的暫存設定，清空帳密及登入憑證；原有 `settings.json` 未更動。
- 呼叫專案現有的 `ticketplus_date_auto_select()` 與 `ticketplus_order()`；
  驗證碼及專屬問答處理停用，未接受條款、未送出訂單、未付款。
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
`activity_selectors_not_found` 結束。

## 修正與回歸結果

- 正式程式與測試腳本共用 `CONST_TICKETPLUS_DATE_ROW_SELECTOR`，使用上列相容選取器。
- 初始化場次計數，元素查詢發生例外時不再使用未定義變數；既有篩選與排序不變。
- 本機 Chrome 載入離線 HTML 的 13 項回歸測試全部通過，涵蓋新舊結構、多場次、
  日期與排除關鍵字、排序、售完與停用按鈕、空列表、查詢例外及張數驗收。
- 測試腳本等待選票頁就緒，最多重試 120 秒；成功必須確認原程式實際操作的
  一般票種容器內張數為 1，不接受其他票種的數字 1 或全頁查詢的模糊結果。
- VERA 活動修正後首次停在 `needs_manual_login`；使用者手動登入後，
  原測試流程自動繼續，最終結果為 `quantity_selected`，程式以 0 正常結束：

  ```json
  {
    "date_selector_count": 1,
    "date_selected": true,
    "order_page_reached": true,
    "ticket_number_assigned": true,
    "selected_ticket": {"ticket_type": "全票\nNT. 2,480\n1", "quantity": 1},
    "captcha_tested": false,
    "order_submitted": false
  }
  ```

- 本機 `ticket-selection.png` 顯示「夢境邊界」全票 NT$2,480、張數 1，
  與程式記錄的實際票種容器一致；截圖含登入畫面資訊，僅保留本機，不提交 GitHub。
- 展開票區時，原生點擊曾被畫面元素遮擋；專案既有的 JavaScript 備援完成展開，
  並成功填入張數。本次沒有新增繞過流程或修改該備援邏輯。
- 正式購票函式介面與設定檔格式不變；本輪未修改 nodriver 或其他平台。

## 尚未驗證

- 自動輸入帳密，以及其他帳號或登入方式；本次由使用者手動登入。
- 其他活動、票型、實名制流程及事件專屬問答。
- 圖片驗證碼辨識與服務端驗證。
- 訂單、座位保留及付款流程。

## 在其他主機重跑

離線回歸測試（測試資料皆為本機 HTML，不會連線售票服務）：

```sh
python -m unittest discover -s tests -v
```

先同步任務分支並準備專案 Python 依賴，選擇當下仍可購票的公開活動頁：

```sh
python tools/ticketplus_smoke_test.py --url https://ticketplus.com.tw/activity/EVENT_ID
```

如需讓使用者在測試 Chrome 視窗手動登入，可加上
`--login-wait-seconds 900`，最多等待 15 分鐘。腳本不會自動輸入帳密，
也不會解驗證碼、接受條款或送出訂單。正常填入一張票時回傳 0；
登入待處理、逾時或選場／選票失敗時回傳非 0。
