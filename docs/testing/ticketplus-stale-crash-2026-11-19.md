# 遠大選票頁自動關閉：2026-11-19

## 已確認原因

活動：[使用者回報的遠大活動](https://ticketplus.com.tw/activity/75a694bf61cb28f0e24835916cfae36e)。
使用者提供完整 Terminal 堆疊，確認當次程式的退出點是：

```text
main -> ticketplus_main -> ticketplus_order
next_step_button.is_enabled()
StaleElementReferenceException: stale element not found in the current frame
```

執行版本是 main `d564998`，Python 3.12.16、Selenium、Chrome 157.0.8103.79。
已進入 `/order/` 選票頁並展開票區；程式找到下一步後，頁面換掉了該元素，
讀取舊按鈕狀態時發生 stale reference。這一行沒有捕捉例外，遠大主迴圈當時也沒有
重試保護，因此錯誤直接傳到 CLI，Python 結束，使用者看到自動化瀏覽器一併關閉。

[Selenium 官方說明](https://www.selenium.dev/documentation/webdriver/troubleshooting/errors/#staleelementreferenceexception)
指出頁面 DOM 更新會使先前取得的元素引用失效，需要重新定位元素。
本次在本機瀏覽器重現了同一例外、同一正式函式、同一個 `is_enabled()` 呼叫點。
完整堆疊足以確認這次退出原因；不將它推論為所有 Chrome 關閉事件的共同原因。

## 修正與整合

- 從 main 建立 `codex/ticketplus-stale-crash-fix-20261119`。
- 整合既有遠端 `codex/gui-startup-refresh-fix`（`00a8ecf`），
  包含換頁暫時性例外重試、遠大刷新最低間隔、正確的 Selenium Manager 回退，
  以及 GUI 啟動／執行失敗提示和本機遮蔽日誌。這些修正原本尚未進入 main。
- 針對這次確定的錯誤點額外捕捉 `StaleElementReferenceException`：
  按鈕在查詢後被替換時結束當次操作，下一個主迴圈重新定位，瀏覽器保持運作。
  連續更新不會累積成外層換頁重試上限；沒有使用舊引用繼續點擊。
- 既有張數、票種、彈窗、驗證碼及重複送出條件保持生效。
  真正失效的 session 仍會停止並回報，不會無限制忽略所有驅動錯誤。
- 新日誌監控以 UTF-8 讀取子程序輸出，因此也明確指定被監控子程序的
  `PYTHONIOENCODING=utf-8`，避免 Windows 本地碼頁或 ASCII 覆寫造成中文日誌錯誤。
  這是日誌功能的相容處理，不是此次使用者原始堆疊的根因。

目前本機刷新間隔為 0 秒，舊刷新路徑缺少一致節流；
整合的保護會在執行時至少間隔 1 秒，保留更長的使用者間隔。
沒有更改 `settings.json`，也沒有證據把當次 DOM 替換唯一歸因於自動刷新。

## 回歸驗證

新增本機 DOM 案例：在 Selenium 查到且確認下一步可見之後，
立刻以 clone 替換該按鈕，接著讓正式選票函式繼續讀取狀態。

- 修正前：第一輪在 `next_step_button.is_enabled()` 拋出與使用者一致的 stale 例外。
- 修正後：連續六輪 DOM 替換皆正常返回等待，瀏覽器仍可讀取、沒有點下一步；
  停止替換後，下一輪取得新按鈕並只點擊一次。
- 另以真實子程序、ASCII 輸出環境重現中文日誌錯誤；修正後正常退出且中文完整保存。
- 完整 104 項回歸測試通過，涵蓋既有選票／確認流程、GUI 啟動、憑證遮蔽、
  有限次換頁重試、真正 session 失效、刷新節流及上述新增案例。
- 另完成 Python 編譯與 Git whitespace 檢查。

測試只使用本機 HTML、模擬庫存回應及隔離子程序，沒有向活動頁送出購票操作、
接受實站條款、建立新訂單或付款。沒有重新執行本場完整實站購票驗收。
測試輸出保留於本機忽略的 `.tools/stale-crash-before.log` 與
`.tools/stale-crash-all-tests.log`；使用者設定及登入憑證不提交。

## 套用方式

本機程式已更新。需要關閉舊 GUI 與機器人，再使用
`.venv\Scripts\python.exe settings.py` 重新開啟。
更新後 GUI 會顯示啟動／停止／失敗及 `%TEMP%` 中的日誌路徑，方便取得後續錯誤。
