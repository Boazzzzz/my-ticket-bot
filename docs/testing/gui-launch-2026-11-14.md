# GUI 啟動與遠大一張票實測：2026-11-14

## 結論

GUI 執行按鈕有啟動搶票子程序；本機實測從遠大首頁進入 K-WONDER
活動及選票頁，正式選票函式將「橙207區／全票 NT$6,680」填入一張。
到此停止，沒有按選票頁的下一步、接受條款、建立訂單或付款。

按下後長時間沒有瀏覽器的現象已重現。12 次啟動的量測為
304.4～307.6 秒，日誌均出現 Selenium Manager 查詢下列版本資料逾時，
隨後使用快取驅動的警告：

`https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json`

此結果確認本次啟動延遲的原因；沒有證據將先前活動頁刷新後 Chrome 關閉
也歸因於同一問題。本輪未修改正式啟動器或驅動取得邏輯。

## 測試方式與範圍

- 使用者本輪確認範圍為一張票，填入後停止。
- GUI 使用專案 `.venv` Python 3.13.15，Chrome 157、Selenium 引擎。
- 桌面工具無法取得未列出的 Python GUI 視窗，因此以本機診斷包裝器開啟
  `settings.main_gui()`，透過 Tk 事件迴圈呼叫實際 `btn_run.invoke()`，
  經原有存檔、`settings.launch_maxbot()`、`util.launch_maxbot()` 路徑啟動。
- 啟動子程序使用診斷入口載入正式 `chrome_tixcraft` CLI／主迴圈，
  額外記錄啟動時間、追蹤正式張數函式實際操作的票種、截圖並在成功後退出。
- GUI 另存本機測試設定，固定一張、OCR 關閉、掛機送出關閉、擴充套件關閉；
  禁止條款、確認頁及活動提示自動接受。測試瀏覽器保留預設安全防護。
- 沿用設定中的遠大登入流程，由首頁登入後導向既有活動；未輸出或提交帳密。
- 測試未覆寫使用者 `settings.json`；暫存設定中的憑證副本於完成後刪除。

活動：
[2026 K-WONDER TRIANGLE 高雄場](https://ticketplus.com.tw/activity/f79e13ad9885c42f0f8103d9716e9b15)

選票場次路由：
`/order/f79e13ad9885c42f0f8103d9716e9b15/9b2626a1594892a389486b0d5ee3d649`

實際操作票種的驗收摘要：

```json
{
  "status": "quantity_selected",
  "selected_ticket": {
    "ticket_type": "橙207區／全票 NT$6,680",
    "quantity": 1
  },
  "order_submitted": false,
  "terms_accepted": false
}
```

## 重複啟動與限制

測試 GUI 開啟期間收到多次執行按鈕事件，合計啟動 12 個子程序；原 GUI
允許啟動多個瀏覽器，也沒有顯示這段驅動等待狀態。10 個程序記錄到同票種
一張後退出，另有程序最後進入網站 `blocked.html` 或逾時。因此不能宣稱
所有重試都通過，也不能將網站封鎖推定為程式選票選取器錯誤。

完成後已停止診斷 GUI 及其仍存活的子程序；未停止使用者原有 GUI。
含會員畫面的原始截圖、詳細日誌與診斷腳本僅保留在忽略的 `.tools/`，
不提交 GitHub。主要證據為 `.tools/gui-live/one-ticket.png`、
`.tools/gui-live/result.json` 及 `.tools/gui-retry-bot.log`。

本輪驗證 GUI 啟動及選票張數，沒有驗證下一步、驗證碼、訂單建立或付款。
後續修正應評估驅動查詢等待時間及 GUI 啟動狀態提示，並保留 Chrome
更新後取得相容驅動的能力。
