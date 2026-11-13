# K-WONDER 選完張數不前進：2026-11-13

## 問題與結論

使用者回報 [2026 K-WONDER TRIANGLE 高雄場](https://ticketplus.com.tw/activity/f79e13ad9885c42f0f8103d9716e9b15)
即使開啟掛機模式，Selenium 選好兩張後仍不按下一步。
本次直接觀察使用者仍在執行的選票頁，確認是隱藏的 Vuetify 登入彈窗被誤判為開啟，
不是只有掛機設定問題。已修正正式程式的彈窗判斷。

## 實際停滯條件

頁面為 2026-11-29 13:00 加場的 `/order/` 路由。只讀檢查確認：

- `ocr_captcha.force_submit` 為 true，設定張數為 2。
- 可見張數為 2，正式 `ticketplus_order_ticket_count_matches()` 回傳 true。
- 沒有可見驗證碼，正式驗證碼判斷回傳 false。
- 兩層頁尾結構的「下一步」可見、可用，文字正確。
- 唯一被舊判斷當成阻擋的彈窗，外層 `is_displayed()` 為 true、文字為空，
  內層登入面板則是 `display: none`。

匿名化的關鍵結構：

```html
<div role="dialog" aria-modal="true" class="v-dialog__content">
  <div class="v-dialog height90 v-dialog--fullscreen" style="display: none">
    <!-- 已關閉的登入介面 -->
  </div>
</div>
```

Vuetify 保留外層容器，`aria-modal="true"` 不能單獨證明面板仍在開啟。
原程式只對外層呼叫 `is_displayed()`，因此每輪都跳過下一步。

## 修正

新增 `ticketplus_order_has_blocking_dialog()`：仍先檢查彈窗可見性；
若是 Vuetify 的 `.v-dialog__content`，再檢查其實際 `.v-dialog` 面板。
只有明確找到面板且所有面板均隱藏時，才忽略該殘留容器。
真正可見的面板、一般 modal、其他 active dialog 與查詢例外仍阻擋前進。
沒有用「文字為空」判斷彈窗關閉，因此空白載入面板也不會被忽略。

不改張數／票種驗收、掛機模式、驗證碼、專屬問答或重複提交防護。
使用者既有 `settings.json` 不包含在提交中。

## 驗證

- 依實際固定滿版容器結構建立回歸頁；舊版在「應按下一步」的斷言失敗，
  修正版會點一次下一步。
- 新增五項回歸情境：已隱藏登入面板、可見的空面板、同時存在其他 active dialog、
  一般空 modal、彈窗查詢失敗。
- 全部 52 項既有及新增離線測試通過；另通過 Python 編譯與 Git whitespace 檢查。
- 在使用者同一個仍卡住的實站頁面呼叫修正版正式函式，攔截所有元素點擊，
  確認只嘗試點擊一次「下一步」；沒有向瀏覽器傳送點擊，路由保持原選票頁。

本機實站攔截摘要：

```json
{
  "legacy_dialog_blocked": true,
  "fixed_dialog_blocked": false,
  "expected_quantity": 2,
  "count_matches": true,
  "intercepted_clicks": ["下一步"],
  "click_sent_to_browser": false,
  "order_submitted": false
}
```

這次沒有實際送出配票或新訂單，不能據此宣稱本場完整結帳通過。
執行中的舊機器人已載入舊函式，需停止後重新啟動才能套用修正。
原始頁面擷取、實站截圖與診斷腳本只保留本機 `.tools/`，不提交帳密或會員資訊。
