"""Confirm seats and contact details on local DOMs; never contact TicketPlus."""

from pathlib import Path
import sys
import unittest
from unittest.mock import PropertyMock, patch
from urllib.parse import quote

from selenium import webdriver

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chrome_tixcraft as bot


class TicketPlusConfirmationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        options = webdriver.ChromeOptions()
        options.add_argument('--headless=new')
        cls.driver = webdriver.Chrome(options=options)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def setUp(self):
        self.config = {'advanced': {'verbose': False}, 'ocr_captcha': {'force_submit': True}}
        bot.ticketplus_dict = {'fail_list': [], 'is_popup_confirm': False}

    def load(self, terms=False, disabled=False, extra='', button_text='下一步'):
        checkbox = ('<div class="v-input__slot"><div><input id="terms" type="checkbox" '
                    'onclick="document.getElementById(\'next\').disabled=!this.checked">'
                    '</div></div>') if terms else ''
        html = ('<!doctype html><meta charset="utf-8"><script>window.nextClicks=0</script>'
                + checkbox + '<button id="next" class="nextBtn" '
                + ('disabled ' if disabled else '')
                + 'onclick="window.nextClicks++">' + button_text + '</button>' + extra)
        self.driver.get('data:text/html;charset=utf-8,' + quote(html))

    def run_confirm(self, path='/confirmSeat/event/session', host='ticketplus.com.tw', state=None):
        with patch.object(type(self.driver), 'current_url', new_callable=PropertyMock,
                          return_value='https://' + host + path):
            if state is None:
                return bot.ticketplus_confirm(self.driver, self.config)
            return bot.ticketplus_confirm(self.driver, self.config, state)

    def clicks(self):
        return self.driver.execute_script('return window.nextClicks')

    def test_seat_confirmation_advances_without_terms_checkbox(self):
        self.load()
        self.assertTrue(self.run_confirm())
        self.assertEqual(self.clicks(), 1)

    def test_contact_checks_terms_and_advances_when_button_becomes_enabled(self):
        self.load(terms=True, disabled=True)
        self.assertTrue(self.run_confirm('/confirm/event/session'))
        self.assertTrue(self.driver.find_element('id', 'terms').is_selected())
        self.assertEqual(self.clicks(), 1)

    def test_manual_mode_retains_terms_fill_without_next(self):
        self.load(terms=True, disabled=True)
        self.config['ocr_captcha']['force_submit'] = False
        self.assertFalse(self.run_confirm('/confirm/event/session'))
        self.assertTrue(self.driver.find_element('id', 'terms').is_selected())
        self.assertEqual(self.clicks(), 0)

    def test_contact_requires_checked_terms(self):
        self.load()
        self.assertFalse(self.run_confirm('/confirm/event/session'))
        self.assertEqual(self.clicks(), 0)

    def test_failed_terms_check_does_not_advance(self):
        self.load(terms=True)
        with patch.object(bot, 'force_check_checkbox', return_value=True):
            self.assertFalse(self.run_confirm('/confirm/event/session'))
        self.assertEqual(self.clicks(), 0)

    def test_disabled_button_does_not_advance(self):
        self.load(disabled=True)
        self.assertFalse(self.run_confirm())
        self.assertEqual(self.clicks(), 0)

    def test_unfilled_required_contact_field_blocks_progress(self):
        self.load(terms=True, extra='<input required aria-label="姓名">')
        self.assertFalse(self.run_confirm('/confirm/event/session'))
        self.assertEqual(self.clicks(), 0)

    def test_invalid_email_blocks_progress(self):
        self.load(terms=True, extra='<input type="email" value="invalid">')
        self.assertFalse(self.run_confirm('/confirm/event/session'))
        self.assertEqual(self.clicks(), 0)

    def test_vue_validation_error_blocks_progress(self):
        self.load(terms=True, extra='<input aria-invalid="true">')
        self.assertFalse(self.run_confirm('/confirm/event/session'))
        self.assertEqual(self.clicks(), 0)

    def test_hidden_login_validation_does_not_block(self):
        self.load(terms=True, extra='<input type="email" required style="display:none">')
        self.assertTrue(self.run_confirm('/confirm/event/session'))
        self.assertEqual(self.clicks(), 1)

    def test_active_dialog_blocks_progress(self):
        self.load(extra='<div class="v-dialog--active">請確認</div>')
        self.assertFalse(self.run_confirm())
        self.assertEqual(self.clicks(), 0)

    def test_closed_vuetify_login_panel_does_not_block(self):
        self.load(extra='<div role="dialog" aria-modal="true" class="v-dialog__content" '
                        'style="position:fixed;inset:0;pointer-events:none">'
                        '<div class="v-dialog" style="display:none"></div></div>')
        self.assertTrue(self.run_confirm())
        self.assertEqual(self.clicks(), 1)

    def test_captcha_stops_confirmation(self):
        self.load(extra='<input placeholder="請輸入驗證碼">')
        self.assertFalse(self.run_confirm())
        self.assertEqual(self.clicks(), 0)

    def test_checkout_and_other_routes_are_untouched(self):
        for path in ('/checkout/event/session', '/order/event/session', '/done/123',
                     '/confirm/event', '/confirm/event/session/extra'):
            with self.subTest(path=path):
                self.load(terms=True, button_text='前往付款')
                self.assertFalse(self.run_confirm(path))
                self.assertFalse(self.driver.find_element('id', 'terms').is_selected())
                self.assertEqual(self.clicks(), 0)

    def test_other_host_is_untouched(self):
        self.load()
        self.assertFalse(self.run_confirm(host='example.com'))
        self.assertEqual(self.clicks(), 0)

    def test_only_one_visible_exact_next_button_is_clicked(self):
        self.load(extra='<button class="nextBtn" style="display:none">下一步</button>'
                        '<button class="nextBtn">使用</button>')
        self.assertTrue(self.run_confirm())
        self.assertEqual(self.clicks(), 1)

    def test_duplicate_visible_next_buttons_do_not_advance(self):
        self.load(extra='<button class="nextBtn">下一步</button>')
        self.assertFalse(self.run_confirm())
        self.assertEqual(self.clicks(), 0)

    def test_same_page_is_not_submitted_twice(self):
        self.load()
        self.assertTrue(self.run_confirm())
        self.assertFalse(self.run_confirm())
        self.assertEqual(self.clicks(), 1)

    def test_next_phase_can_advance_without_waiting_for_previous_phase_cooldown(self):
        self.load()
        self.assertTrue(self.run_confirm())
        self.load(terms=True, disabled=True)
        self.assertTrue(self.run_confirm('/confirm/event/session'))
        self.assertEqual(self.clicks(), 1)

    def test_element_query_error_does_not_advance(self):
        self.load()
        with patch.object(self.driver, 'find_elements', side_effect=bot.WebDriverException('query failed')):
            self.assertFalse(self.run_confirm())
        self.assertEqual(self.clicks(), 0)

    def test_main_advances_confirmation_steps_and_stops_at_checkout(self):
        for path in ('/confirmSeat/event/session', '/confirm/event/session', '/checkout/event/session'):
            with self.subTest(path=path):
                contact = path.startswith('/confirm/')
                checkout = path.startswith('/checkout/')
                self.load(terms=contact, disabled=contact,
                          button_text='前往付款' if checkout else '下一步')
                url = 'https://ticketplus.com.tw' + path
                with patch.object(type(self.driver), 'current_url', new_callable=PropertyMock, return_value=url), \
                        patch.object(bot, 'play_sound_while_ordering'):
                    bot.ticketplus_main(self.driver, url, self.config, None, None)
                self.assertEqual(self.clicks(), 0 if checkout else 1)


if __name__ == '__main__':
    unittest.main()
