"""Exercise ticket-selection progression against local browser DOMs only."""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import quote

from selenium import webdriver

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chrome_tixcraft as bot


class TicketPlusOrderProgressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        options = webdriver.ChromeOptions()
        options.add_argument('--headless=new')
        cls.driver = webdriver.Chrome(options=options)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def setUp(self):
        self.config = {
            'advanced': {'verbose': False, 'auto_reload_page_interval': 0},
            'ticket_number': 1,
            'area_auto_select': {'area_keyword': '', 'mode': 'from top to bottom'},
            'keyword_exclude': '"身障"',
            'ocr_captcha': {'enable': False, 'force_submit': True},
        }
        self.state = {'fail_list': []}

    def load(self, count=1, style=2, disabled=False, extra='', label='GA NT.1,800'):
        button = '<button id="next" class="nextBtn" %s onclick="window.nextClicks++">下一步</button>' % ('disabled' if disabled else '')
        if style == 1:
            button = '<div class="row"><div>' + button + '</div></div>'
        page = '''<!doctype html><meta charset="utf-8"><script>window.nextClicks=0</script>
            <div class="rwd-margin"><div class="text-title"><span>%s</span>
            <div class="count-button"><div id="count">%s</div>
            <button onclick="document.getElementById('count').textContent=1;document.getElementById('next').disabled=false">
            <span><i class="mdi-plus">+</i></span></button></div></div></div>
            <div class="order-footer"><div class="container"><div class="row"><div>%s</div></div></div></div>%s
        ''' % (label, count, button, extra)
        self.driver.get('data:text/html;charset=utf-8,' + quote(page))

    def run_order(self):
        return bot.ticketplus_order(self.driver, self.config, None, None, self.state)[0]

    def next_clicks(self):
        return self.driver.execute_script('return window.nextClicks')

    def test_ready_ticket_without_captcha_advances_in_away_mode(self):
        self.load()
        self.assertTrue(self.run_order())
        self.assertEqual(self.next_clicks(), 1)

    def test_nested_footer_also_advances(self):
        self.load(style=1)
        self.assertTrue(self.run_order())
        self.assertEqual(self.next_clicks(), 1)

    def test_assigning_quantity_can_enable_and_press_next(self):
        self.load(count=0, disabled=True)
        self.assertTrue(self.run_order())
        self.assertEqual(self.driver.find_element('id', 'count').text, '1')
        self.assertEqual(self.next_clicks(), 1)

    def load_replaced_quantity_controls(self, count=0):
        self.load(count=count, disabled=count == 0)
        self.driver.execute_script("""
window.testCount = arguments[0];
window.counterRoot = document.querySelector('.count-button');
window.renderCounter = () => {
  window.counterRoot.innerHTML =
    '<div id="count">' + window.testCount + '</div>' +
    '<button onclick="window.testCount++;window.renderCounter()"><span><i class="mdi-plus">+</i></span></button>';
  document.getElementById('next').disabled = window.testCount === 0;
};
window.renderCounter();
""", count)

    def test_partial_quantity_continues_even_when_next_already_enabled(self):
        self.load_replaced_quantity_controls(count=1)
        self.config['ticket_number'] = 2
        self.assertTrue(self.run_order())
        self.assertEqual(self.driver.find_element('id', 'count').text, '2')
        self.assertEqual(self.next_clicks(), 1)

    def test_quantity_control_replacement_does_not_stall_two_ticket_selection(self):
        self.load_replaced_quantity_controls()
        self.config['ticket_number'] = 2
        for _ in range(3):
            if self.run_order(): break
        self.assertEqual(self.driver.find_element('id', 'count').text, '2')
        self.assertEqual(self.next_clicks(), 1)

    def test_partial_quantity_in_manual_mode_fills_without_submitting(self):
        self.load_replaced_quantity_controls(count=1)
        self.config.update(ticket_number=2)
        self.config['ocr_captcha']['force_submit'] = False
        self.assertFalse(self.run_order())
        self.assertEqual(self.driver.find_element('id', 'count').text, '2')
        self.assertEqual(self.next_clicks(), 0)

    def test_two_tickets_without_captcha_advances_with_ocr_enabled(self):
        self.load(count=2)
        self.config['ticket_number'] = 2
        self.config['ocr_captcha']['enable'] = True
        self.assertTrue(self.run_order())
        self.assertEqual(self.next_clicks(), 1)

    def test_partial_quantity_with_disabled_plus_stays_and_reports_counts(self):
        self.load_replaced_quantity_controls(count=1)
        self.config['ticket_number'] = 2
        self.driver.execute_script("document.querySelector('.count-button button').disabled=true")
        self.assertFalse(self.run_order())
        self.assertEqual(self.state['order_progress_reason'], 'quantity_or_area_mismatch')
        self.assertIn('"observed": [1]', self.state['order_progress'])
        self.assertEqual(self.next_clicks(), 0)

    def test_partial_wrong_ticket_keyword_does_not_increase_or_submit(self):
        self.load_replaced_quantity_controls(count=1)
        self.config['ticket_number'] = 2
        self.config['area_auto_select']['area_keyword'] = '"9999"'
        self.assertFalse(self.run_order())
        self.assertEqual(self.driver.find_element('id', 'count').text, '1')
        self.assertEqual(self.next_clicks(), 0)

    def test_partial_excluded_ticket_is_not_increased_or_submitted(self):
        self.load_replaced_quantity_controls(count=1)
        self.config['ticket_number'] = 2
        self.driver.execute_script("document.querySelector('.text-title > span').textContent='身障 NT.1800'")
        self.assertFalse(self.run_order())
        self.assertEqual(self.state['order_progress_reason'], 'selected_ticket_excluded')
        self.assertEqual(self.driver.find_element('id', 'count').text, '1')
        self.assertEqual(self.next_clicks(), 0)

    def test_partial_second_ticket_row_is_completed_without_selecting_first_row(self):
        self.load_replaced_quantity_controls(count=1)
        self.config['ticket_number'] = 2
        self.driver.execute_script("""
const row=document.createElement('div');row.className='text-title';
row.innerHTML='<span>Other ticket</span><div class="count-button"><div id="otherCount">0</div><button><span><i class="mdi-plus">+</i></span></button></div>';
document.querySelector('.rwd-margin').prepend(row);
""")
        self.assertTrue(self.run_order())
        self.assertEqual(self.driver.find_element('id', 'count').text, '2')
        self.assertEqual(self.driver.find_element('id', 'otherCount').text, '0')
        self.assertEqual(self.next_clicks(), 1)

    def test_quantity_over_target_is_not_increased_or_submitted(self):
        self.load_replaced_quantity_controls(count=3)
        self.config['ticket_number'] = 2
        self.assertFalse(self.run_order())
        self.assertEqual(self.driver.find_element('id', 'count').text, '3')
        self.assertEqual(self.next_clicks(), 0)

    def test_unchanged_progress_reason_does_not_flood_logs(self):
        with patch('builtins.print') as output, patch.object(bot.time, 'monotonic', return_value=1):
            bot.ticketplus_order_progress(self.state, 'blocking_dialog')
            bot.ticketplus_order_progress(self.state, 'blocking_dialog')
        output.assert_called_once()

    def test_manual_mode_does_not_press_next(self):
        self.load()
        self.config['ocr_captcha']['force_submit'] = False
        self.assertFalse(self.run_order())
        self.assertEqual(self.next_clicks(), 0)

    def test_quantity_mismatch_does_not_press_next(self):
        self.load()
        self.config['ticket_number'] = 2
        self.assertFalse(self.run_order())
        self.assertEqual(self.next_clicks(), 0)

    def test_unknown_quantity_does_not_press_next(self):
        self.load(count='載入中')
        self.assertFalse(self.run_order())
        self.assertEqual(self.next_clicks(), 0)

    def test_wrong_selected_price_does_not_press_next(self):
        self.load(label='Earlybird NT.1,500')
        self.config['area_auto_select']['area_keyword'] = '"1800"'
        self.assertFalse(self.run_order())
        self.assertEqual(self.next_clicks(), 0)

    def test_selected_price_matching_uses_existing_comma_normalization(self):
        self.load()
        self.config['area_auto_select']['area_keyword'] = '"1800"'
        self.assertTrue(self.run_order())
        self.assertEqual(self.next_clicks(), 1)

    def test_visible_captcha_never_uses_no_captcha_next(self):
        self.load(extra='<input placeholder="請輸入驗證碼">')
        self.assertFalse(self.run_order())
        self.assertEqual(self.next_clicks(), 0)

    def test_hidden_captcha_does_not_block_no_captcha_flow(self):
        self.load(extra='<input style="display:none" placeholder="請輸入驗證碼">')
        self.assertTrue(self.run_order())
        self.assertEqual(self.next_clicks(), 1)

    def test_ready_button_with_captcha_still_uses_ocr_branch(self):
        self.load(extra='<input placeholder="請輸入驗證碼">')
        self.config['ocr_captcha']['enable'] = True
        with patch.object(bot, 'ticketplus_order_ocr', return_value=False) as ocr:
            self.assertFalse(self.run_order())
        ocr.assert_called_once()
        self.assertEqual(self.next_clicks(), 0)

    def test_captcha_dialog_preserves_existing_ocr_branch(self):
        self.load(extra='<div class="v-dialog--active"><input placeholder="請輸入驗證碼"></div>')
        self.config['ocr_captcha']['enable'] = True
        with patch.object(bot, 'ticketplus_order_ocr', return_value=False) as ocr:
            self.assertFalse(self.run_order())
        ocr.assert_called_once()
        self.assertEqual(self.state['order_progress_reason'], 'captcha_pending')
        self.assertEqual(self.next_clicks(), 0)

    def test_unanswered_activity_question_blocks_progress(self):
        self.load()
        with patch.object(bot, 'ticketplus_order_exclusive_code', return_value=(False, [], True)):
            self.assertFalse(self.run_order())
        self.assertEqual(self.next_clicks(), 0)

    def test_active_dialog_blocks_progress(self):
        self.load(extra='<div class="v-dialog--active">請確認</div>')
        self.assertFalse(self.run_order())
        self.assertEqual(self.next_clicks(), 0)

    def test_visible_vuetify_wrapper_with_closed_login_panel_does_not_block(self):
        self.load(extra='<div role="dialog" aria-modal="true" class="v-dialog__content" '
                        'style="position:fixed;inset:0;pointer-events:none">'
                        '<div class="v-dialog height90 v-dialog--fullscreen" style="display:none">'
                        '<input type="password"></div></div>')
        wrapper = self.driver.find_element('css selector', '.v-dialog__content')
        self.assertTrue(wrapper.is_displayed())
        self.assertFalse(wrapper.find_element('css selector', '.v-dialog').is_displayed())
        self.assertTrue(self.run_order())
        self.assertEqual(self.next_clicks(), 1)

    def test_visible_empty_vuetify_panel_still_blocks(self):
        self.load(extra='<div role="dialog" aria-modal="true" class="v-dialog__content">'
                        '<div class="v-dialog" style="width:100px;height:100px"></div></div>')
        self.assertFalse(self.run_order())
        self.assertEqual(self.next_clicks(), 0)

    def test_closed_login_panel_does_not_hide_another_active_dialog(self):
        self.load(extra='<div role="dialog" aria-modal="true" class="v-dialog__content">'
                        '<div class="v-dialog" style="display:none"></div></div>'
                        '<div class="v-dialog--active">請確認票種</div>')
        self.assertFalse(self.run_order())
        self.assertEqual(self.next_clicks(), 0)

    def test_generic_modal_still_blocks_without_vuetify_panel(self):
        self.load(extra='<div role="dialog" aria-modal="true" '
                        'style="width:100px;height:100px"></div>')
        self.assertFalse(self.run_order())
        self.assertEqual(self.next_clicks(), 0)

    def test_dialog_lookup_failure_blocks_progress(self):
        self.load()
        find_elements = self.driver.find_elements

        def fail_dialog_lookup(by, selector):
            if selector == '.v-dialog--active, [role="dialog"][aria-modal="true"]':
                raise bot.WebDriverException('dialog lookup failed')
            return find_elements(by, selector)

        with patch.object(self.driver, 'find_elements', side_effect=fail_dialog_lookup):
            self.assertFalse(self.run_order())
        self.assertEqual(self.next_clicks(), 0)

    def test_pending_navigation_is_not_clicked_twice(self):
        self.load()
        self.assertTrue(self.run_order())
        self.assertFalse(self.run_order())
        self.assertEqual(self.next_clicks(), 1)

    def test_ocr_helper_returns_observed_submission_result(self):
        self.load(extra='<input placeholder="請輸入驗證碼">')
        self.config['ocr_captcha']['enable'] = True
        with patch.object(bot, 'ticketplus_auto_ocr', return_value=(False, None, True)), \
                patch.object(bot, 'ticketplus_check_and_renew_captcha', return_value=False), \
                patch.object(bot.time, 'sleep'):
            self.assertTrue(bot.ticketplus_order_ocr(self.driver, self.config, None, None))


if __name__ == '__main__':
    unittest.main()
