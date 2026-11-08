# 遠大跨活動流程測試：2026-11-08

## 範圍與目前狀態

使用者授權：另測兩場，每場一般票一張，每張不超過 NT$2,480，建立待付款訂單即停止，
不付款，使用者於測試後手動取消。這個範圍不包含付款或自動取消訂單。

目前不能宣稱兩場都通過：Sweetnotes 已正確選到 GA NT$1,800 一張，並到填寫資料頁，
停在會員服務條款與隱私權政策的當下確認；尚未建立該場訂單。
第二場候選為諏訪ななか Mini Live 的第 1 部 GA 席 NT$2,400，已確認活動頁可購買，
尚未執行選票／建立訂單。兩者目前都沒有完成驗證碼測試。

## 公開活動頁比較

| 活動 | 測試時觀察 | 流程與限制 |
| --- | --- | --- |
| Sweetnotes Asia Tour Live in Kaohsiung | 仍可購買；GA NT$1,800；活動頁列信用卡及 ATM | 實站為選票種、填寫資料、付款三步，沒有 VERA 的獨立確認座位頁 |
| 諏訪ななか Fan Meeting & Mini Live in Taipei | 第 1／2 部各有 VIP 與 GA 場次；GA NT$2,400；活動頁列 ATM | GA 是獨立場次，需先以日期／場次關鍵字指定 GA，不能先選 VIP 場再只改票區關鍵字 |
| hue《RGB》新專輯演唱會 SPLASH | 場次顯示銷售一空 | 無法執行目前訂單測試 |
| MYTH & ROID 台北場 | 顯示銷售一空；購買提醒列信用卡 | 不能推論付款選項與 VERA 相同；未進入付款頁實驗 |
| 甜約翰十週年演唱會 | 原場售完，加場尚未開賣 | 未進入選票頁 |
| Jeff Bernat 台北場 | 尚未開賣 | 未進入選票頁 |
| 2027 CHOSEN FESTIVAL 邱聲 | 可購買；購買提醒列信用卡 | 未進入付款頁，未據此建立待付款訂單 |

公開網址：

- Sweetnotes：https://ticketplus.com.tw/activity/1514ab3dc6de9d16fd775316c8cc60d0
- 諏訪ななか：https://ticketplus.com.tw/activity/90e38a4ec114145802d43a5acaff7e8a
- hue：https://ticketplus.com.tw/activity/132e75d175ce49bb2a96068e980642a0
- MYTH & ROID：https://ticketplus.com.tw/activity/03627ec8454b37cf8fc712b763261a47
- 甜約翰：https://ticketplus.com.tw/activity/9d53a5c4a08674c0d9117bfe64ed78ca
- Jeff Bernat：https://ticketplus.com.tw/activity/e029638fd4f828e6faf160f62d08ae6b
- 邱聲：https://ticketplus.com.tw/activity/9de6b98aa09a42209d45ab15b4cbd097

售票狀態與付款方式以實際操作當下的頁面為準，公告文字不等同最終付款選項。

## 已確認並修正的選票問題

Sweetnotes 是平面票種清單，指定 `1800` 後，原程式首次選票未成功取得指定列，
接著的全頁備援卻操作第一列 Earlybird NT$1,500，造成實際票種與指定 GA 不符。
嚴格張數驗收未將這次當成成功，也沒有按下一步或送出錯誤票種訂單。

後續將 Earlybird 歸零，再呼叫正式選票函式，診斷確認它能找到 GA 列並選到一張；
同頁其他票種張數均為零，才繼續到填寫資料頁。
目前證據不足以判斷首次指定列操作未成功的具體點擊原因；選取器能匹配 GA，
因此本輪沒有憑推測改選取器。

正式程式新增保護：有指定票區關鍵字時，指定列操作失敗會等待下次重試，
不再以全頁第一個加號取代指定票種。空關鍵字的既有備援保持原行為。
修正後尚未重新建立新訂單來驗證整段無人介入流程。

## 診斷工具與回歸檢查

- 待付款診斷工具新增每次執行明確指定 `--approved-price`、`--ticket-label`；
  預設仍為原 VERA 的 NT$2,480「夢境邊界」，維持先前指令相容。
- 活動頁 URL 綁定後續操作，避免已登入視窗轉到其他活動還繼續執行。
- 送單前驗證指定票種、共一張、實際總額、ATM 已選、信用卡未選；不會提交信用卡付款。
- 新增 `--date-keyword` 作為一般文字的場次關鍵字，透過既有日期篩選函式處理。
- 32 項離線測試通過（17 項待付款診斷保護、15 項 DOM／選票回歸），
  另完成 Python 編譯與 Git whitespace 檢查。
- 新增案例涵蓋不同票名／金額、轉到其他活動、指定票名不符，以及指定列失敗時
  不得使用全頁備援；未改其他售票平台或設定檔格式。

範例（仍須操作者逐步檢查畫面並放入單次診斷指令；不會自行接受條款或解驗證碼）：

```sh
python tools/ticketplus_checkout_test.py --url https://ticketplus.com.tw/activity/1514ab3dc6de9d16fd775316c8cc60d0 --approved-price 1800 --ticket-label GA --login-wait-seconds 900
python tools/ticketplus_checkout_test.py --url https://ticketplus.com.tw/activity/90e38a4ec114145802d43a5acaff7e8a --date-keyword 第1部GA席 --approved-price 2400 --ticket-label GA --login-wait-seconds 900
```

帳密、Cookie、會員聯絡資訊、訂單／付款資訊與實站截圖只保留本機，不提交 GitHub。

## GUI 遠大帳密欄位

1. 啟動 `settings.py` GUI，切換「自動填表單」。
2. 在「遠大 帳號」那一列填手機帳號，右側星號遮蔽的欄位填密碼。
3. 按「存檔」，寫入本機 `settings.json` 的 `advanced.ticketplus_account` 與
   `advanced.ticketplus_password`。

GUI 已有這些欄位，不需要另外新增介面；本次已開啟自動填表單頁供使用者自行輸入。
GUI 啟動環境原缺 Tornado，已在本機 `.venv` 補齊，未啟動設定頁的網路伺服器。
使用者稍後已在 GUI 自行存檔；只檢查欄位是否有值，確認帳號與密碼都已保存至本機。
未讀出或輸出帳密內容，尚未驗證使用這份設定自動登入。

密碼目前使用固定 XOR 與 Base64 可逆編碼，並非安全密碼保管庫。
`settings.json` 已被 Git 追蹤，需持續排除個人帳密變更，不能靠新增 ignore 規則保護
已追蹤的檔案；本次提交會排除整份使用者設定。跨主機可同步程式與測試報告，
各主機帳密需另行在本機設定，不能把帳密提交到 GitHub。
