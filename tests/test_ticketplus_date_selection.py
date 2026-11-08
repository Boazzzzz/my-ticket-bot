"""Browser DOM regressions using local data URLs; no ticket service is contacted."""

import copy
from html import escape
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import quote

from selenium import webdriver
from selenium.common.exceptions import WebDriverException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chrome_tixcraft as bot
from tools.ticketplus_smoke_test import TicketSelectionTracker


def session_row(identifier, label, disabled=False):
    disabled_attribute = ' disabled' if disabled else ''
    return (
        '<div class="sesstion-item"><div class="row">'
        f'<span>{escape(label)}</span><button id="{identifier}"{disabled_attribute} '
        'onclick="window.testClicks.push(this.id)">立即購買</button></div></div>'
    )


class TicketPlusDOMTests(unittest.TestCase):
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
            'date_auto_select': {'mode': 'from top to bottom', 'date_keyword': ''},
            'tixcraft': {'pass_date_is_sold_out': True, 'auto_reload_coming_soon_page': False},
            'keyword_exclude': '"身障"',
            'ticket_number': 1,
        }

    def load(self, body):
        html = '<!doctype html><meta charset="utf-8"><script>window.testClicks=[]</script>' + body
        self.driver.get('data:text/html;charset=utf-8,' + quote(html))

    def clicks(self):
        return self.driver.execute_script('return window.testClicks')

    def select(self):
        return bot.ticketplus_date_auto_select(self.driver, copy.deepcopy(self.config))

    def test_legacy_direct_child_structure(self):
        self.load('<div id="buyTicket">' + session_row('legacy', '2026-12-27 一般場') + '</div>')
        self.assertTrue(self.select())
        self.assertEqual(self.clicks(), ['legacy'])

    def test_added_wrappers_and_unrelated_rows(self):
        self.load(session_row('unrelated', '立即購買') + '<div id="buyTicket"><div><div>'
                  + session_row('wrapped', '2026-12-27 一般場') + '</div></div></div>')
        self.assertTrue(self.select())
        self.assertEqual(self.clicks(), ['wrapped'])

    def test_date_keyword_selects_matching_session(self):
        self.load('<div id="buyTicket"><div>' + session_row('first', '2026-12-27')
                  + session_row('second', '2026-12-28') + '</div></div>')
        self.config['date_auto_select']['date_keyword'] = '"2026-12-28"'
        self.assertTrue(self.select())
        self.assertEqual(self.clicks(), ['second'])

    def test_unmatched_date_keyword_does_not_click(self):
        self.load('<div id="buyTicket">' + session_row('first', '2026-12-27') + '</div>')
        self.config['date_auto_select']['date_keyword'] = '"2026-12-28"'
        self.assertFalse(self.select())
        self.assertEqual(self.clicks(), [])

    def test_bottom_to_top_order_is_preserved(self):
        self.load('<div id="buyTicket">' + session_row('first', '2026-12-27')
                  + session_row('last', '2026-12-28') + '</div>')
        self.config['date_auto_select']['mode'] = 'from bottom to top'
        self.assertTrue(self.select())
        self.assertEqual(self.clicks(), ['last'])

    def test_sold_out_and_excluded_sessions_are_skipped(self):
        self.load('<div id="buyTicket">' + session_row('soldout', '銷售一空')
                  + session_row('excluded', '會員限定') + session_row('regular', '一般場') + '</div>')
        self.config['keyword_exclude'] = '"會員限定"'
        self.assertTrue(self.select())
        self.assertEqual(self.clicks(), ['regular'])

    def test_disabled_button_is_not_clicked(self):
        self.load('<div id="buyTicket">' + session_row('disabled', '一般場', disabled=True) + '</div>')
        self.assertFalse(self.select())
        self.assertEqual(self.clicks(), [])

    def test_empty_session_list_can_be_retried(self):
        self.load('<div id="buyTicket"></div>')
        self.assertFalse(self.select())
        self.assertEqual(self.clicks(), [])
        self.load('<div id="buyTicket"><div>' + session_row('loaded', '一般場') + '</div></div>')
        self.assertTrue(self.select())
        self.assertEqual(self.clicks(), ['loaded'])

    def test_lookup_exception_does_not_leave_count_uninitialized(self):
        self.load('<div id="buyTicket"></div>')
        with patch.object(self.driver, 'find_elements', side_effect=WebDriverException('test lookup failure')):
            self.assertFalse(self.select())
        self.assertEqual(self.clicks(), [])

    def load_quantity_page(self, label='一般票 NT$600'):
        self.load('<div class="count-button"><div>1</div></div>'
                  '<div id="target" class="text-title">' + escape(label)
                  + '<div class="count-button"><div id="target-count">0</div>'
                  '<button onclick="document.getElementById(\'target-count\').textContent=1">'
                  '<span><i class="mdi-plus">+</i></span></button></div></div>')

    def test_unrelated_quantity_does_not_make_smoke_test_pass(self):
        self.load_quantity_page()
        tracker = TicketSelectionTracker(self.driver, bot.ticketplus_assign_ticket_number)
        self.assertTrue(tracker(self.driver, self.config))
        self.assertIsNone(tracker.snapshot())
        self.assertEqual(self.driver.find_element(bot.By.ID, 'target-count').text, '0')

    def test_selected_ticket_container_must_have_one_ticket(self):
        self.load_quantity_page()
        target = self.driver.find_element(bot.By.ID, 'target')
        tracker = TicketSelectionTracker(self.driver, bot.ticketplus_assign_ticket_number)
        self.assertTrue(tracker(target, self.config))
        selection = tracker.snapshot()
        self.assertEqual(selection['quantity'], 1)
        self.assertIn('一般票 NT$600', selection['ticket_type'])

    def test_restricted_ticket_does_not_satisfy_general_ticket_acceptance(self):
        self.load_quantity_page(label='身障優惠票')
        tracker = TicketSelectionTracker(self.driver, bot.ticketplus_assign_ticket_number)
        self.assertTrue(tracker(self.driver.find_element(bot.By.ID, 'target'), self.config))
        self.assertIsNone(tracker.snapshot())

    def test_replaced_ticket_container_is_retried(self):
        self.load_quantity_page()
        tracker = TicketSelectionTracker(self.driver, bot.ticketplus_assign_ticket_number)
        tracker(self.driver.find_element(bot.By.ID, 'target'), self.config)
        self.load_quantity_page()
        self.assertIsNone(tracker.snapshot())


if __name__ == '__main__':
    unittest.main()
