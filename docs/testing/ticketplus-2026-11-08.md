# 遠大售票功能測試：2026-11-08

## 結論

Selenium 版本原本的自動選場失敗已修正。本次實測已完成驗收：自動選場、
使用者手動登入後進入選票頁、自動選擇「夢境邊界」全票 NT$2,480 並填入 1 張。
第一階段在選票頁停止；使用者後續擴大授權後，第二階段已建立同票種、
同金額的一筆 ATM 待付款訂單，未付款，取消由使用者手動處理。
第二階段全程未出現圖片驗證碼，因此自動辨識、填入及服務端驗證仍未通過驗收。
選票由正式函式操作，後續訂單步驟由操作者逐步指令執行，不能據此宣稱正式程式
已具備完整自動結帳能力；付款也未驗證。
nodriver 版本的遠大選場、選票及驗證碼流程仍有 TODO，不能當作已完成的替代方案。

## 第一階段：測試環境與範圍

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
- 圖片驗證碼辨識、填入與服務端驗證：本活動第二階段沒有出現驗證碼。
- 正式程式無人介入的完整結帳流程、實際付款及取消訂單結果。

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


## 第二階段：依使用者授權建立待付款訂單

使用者明確指定沿用 VERA「夢境邊界」全票 NT$2,480 × 1 張，建立待付款訂單即停止，
不付款，測後自行取消。登入由使用者在測試 Chrome 手動完成；資料確認頁的
「會員服務條款與隱私權政策」經使用者在該步明確同意後才勾選並繼續。
自動審查曾沿用舊範圍阻擋座位確認，重新取得本輪明確授權後才繼續。

實測路徑與結果：

1. 正式選場／選票函式成功選到「夢境邊界」全票 1 張，NT$2,480。
2. 選票頁「下一步」經排隊後進入 `/confirmSeat/`，確認座位成功。
3. 座位頁「下一步」進入 `/confirm/`，確認明細為共 1 張、合計 NT$2,480。
4. 接受使用者核准的條款後進入 `/checkout/`；取票方式選 7-11 ibon，付款方式選 ATM 虛擬帳號。
5. 確認 ATM 已選、信用卡未選、總金額仍為 NT$2,480 後，按「前往付款」。
   此處產生 ATM 待繳款資訊，未執行轉帳或信用卡付款。
6. 回應頁標題為「訂單成立」，顯示「您的訂單已成立！」、繳款期限、ATM 虛擬帳號、
   同票種及 NT$2,480，確認待付款訂單建立成功。測試未取消該筆訂單，交由使用者處理。

畫面另告知日後超商取票每筆需現金支付 NT$30 手續費；本輪未取票、未支付該費用。
從選票、確認座位、確認資料、付款方式到訂單成立都沒有出現驗證碼；因此沒有呼叫 OCR、
沒有填入驗證碼，也沒有證據可以驗收 OCR 正確率或服務端驗證。

本機證據包含 `checkout-atm-selected.png`、`checkout-unpaid-order.png`、
`checkout-unpaid-order.txt` 與 `checkout-observed-result.json`；後者記錄：

```json
{
  "unpaid_order_created": true,
  "order_submitted": true,
  "payment_submitted": false,
  "captcha_tested": false,
  "verification_source": "reviewed_order_confirmation_snapshot"
}
```

證據含訂單及繳款資訊，只保留本機，不提交 GitHub，也不在報告記錄訂單編號或銀行帳號。
這是人工逐步控制 Selenium 的實站結果；沒有重跑新增工具的完整自動流程來建立第二筆訂單。

### 診斷工具與檢查

新增 `tools/ticketplus_checkout_test.py`，沿用安全選票腳本，在選到指定金額一張票後暫停，
每個後續動作都必須由操作者在輸出的暫存目錄放入單次 `request.json` 指令；不會自行付款、
接受條款或解驗證碼。原選票腳本的預設命令列行為不變。

```sh
python tools/ticketplus_checkout_test.py --url https://ticketplus.com.tw/activity/146cbb24e0128239e2c80db2c63fa417 --login-wait-seconds 900
```

指令包含 `action` 及畫面中確認的 `expected_url`；以暫存檔寫完後 rename 為 `request.json`，
避免讀取半份 JSON。操作者先閱讀 `checkout-state.json` 及對應截圖，再逐步送出指令。
可用動作為 `inspect`、`next_from_selection`、`confirm_seat`、`accept_terms`、
`confirm_contact`、`select_atm`、`create_unpaid_order`、`record_unpaid_order`、`close`。
`accept_terms` 需提供已確認的 checkbox `selector`；一般按鈕動作提供該步已確認的
`selector` 與 `expected_text`。`create_unpaid_order` 另需明確提供
`approved_total: 2480`、`approved_quantity: 1`、`payment_method: "ATM"`。
`fill_captcha` 僅能在真正出現驗證碼並取得當下授權後使用，這次沒有執行。
指令檔本身不是人類同意的替代品；條款及驗證碼授權由操作者負責取得。

新工具依本次觀察的大小寫路由與付款頁結構設計；送單前檢查實際 radio 狀態、
票種、張數與頁面總額，僅允許產生 ATM 待繳款資訊。按下按鈕只記錄嘗試，
必須再觀察成立頁與未繳款資訊才記錄成功。30 分鐘無指令會結束並關閉測試視窗；
使用者需要取消訂單時應在此之前自行操作。

新增 14 項離線診斷保護測試，加上既有 13 項 DOM 回歸測試，共 27 項全數通過。
涵蓋頁面切換、價格／張數限制、實際 ATM／信用卡選取狀態、付款按鈕限制、
條款前置確認、確認座位大小寫路由，以及「嘗試送出不等於訂單成功」。
