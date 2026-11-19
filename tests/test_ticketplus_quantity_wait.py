"""Wait for real quantity updates on local DOMs, without fixed post-click delays."""
from pathlib import Path
import sys
import unittest
from urllib.parse import quote
from selenium import webdriver

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chrome_tixcraft as bot


class TicketPlusQuantityWaitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        options = webdriver.ChromeOptions()
        options.add_argument('--headless=new')
        cls.driver = webdriver.Chrome(options=options)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def load(self, count='0', disabled=False, replace=False):
        update = ("const old=document.getElementById('count');const fresh=old.cloneNode(true);"
                  "fresh.textContent=Number(old.textContent)+1;old.replaceWith(fresh);"
                  "const b=document.getElementById('plus');b.replaceWith(b.cloneNode(true));") if replace else (
                  "const e=document.getElementById('count');e.textContent=Number(e.textContent)+1;")
        html = ('<!doctype html><div id="target"><div class="count-button"><div id="count">'
                + count + '</div><button id="plus" ' + ('disabled ' if disabled else '')
                + 'onclick="setTimeout(()=>{' + update + '},80)"><span><i class="mdi-plus">+</i>'
                '</span></button></div></div>')
        self.driver.get('data:text/html;charset=utf-8,' + quote(html))
        return self.driver.find_element('id', 'target')

    def test_waits_for_async_quantity_update(self):
        target = self.load()
        self.assertTrue(bot.ticketplus_assign_ticket_number(target, {'ticket_number': 1}))
        self.assertEqual(self.driver.find_element('id', 'count').text, '1')

    def test_reacquires_replaced_counter_and_plus_for_two_tickets(self):
        target = self.load(replace=True)
        self.assertTrue(bot.ticketplus_assign_ticket_number(target, {'ticket_number': 2}))
        self.assertEqual(self.driver.find_element('id', 'count').text, '2')

    def test_disabled_plus_is_not_forced(self):
        target = self.load(disabled=True)
        self.assertFalse(bot.ticketplus_assign_ticket_number(target, {'ticket_number': 1}))
        self.assertEqual(self.driver.find_element('id', 'count').text, '0')

    def test_unreadable_quantity_is_retried_instead_of_crashing(self):
        target = self.load(count='載入中')
        self.assertFalse(bot.ticketplus_assign_ticket_number(target, {'ticket_number': 1}))

    def test_excess_quantity_is_not_accepted(self):
        target = self.load(count='2')
        self.assertFalse(bot.ticketplus_assign_ticket_number(target, {'ticket_number': 1}))


if __name__ == '__main__':
    unittest.main()
