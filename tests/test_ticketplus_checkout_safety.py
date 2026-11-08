"""Verify the paused checkout runner cannot silently turn selection into payment."""

import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import ticketplus_checkout_test as checkout


class CheckoutSafetyTests(unittest.TestCase):
    def run_command(self, command, path='/checkout/event/session',
                    body='夢境邊界 ATM 共 1 張\n總金額\nNT. 2,480', result=None,
                    atm_selected=True, card_selected=False, title='付款結帳'):
        driver = Mock()
        driver.current_url = 'https://ticketplus.com.tw' + path
        driver.find_element.return_value = SimpleNamespace(text=body)
        driver.title = title
        atm, card = Mock(), Mock()
        atm.is_selected.return_value = atm_selected
        card.is_selected.return_value = card_selected
        driver.find_elements.side_effect = lambda by, selector: [atm] if 'ATM' in selector else [card]
        button = Mock()
        button.text = command.get('expected_text', '前往付款')
        command.setdefault('expected_url', driver.current_url)
        result = result if result is not None else {}
        result.setdefault('selected_ticket', {'ticket_type': '全票\nNT. 2,480\n1', 'quantity': 1})
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / 'request.json').write_text(json.dumps(command))
            with patch.object(checkout, 'inspect_page'), \
                    patch.object(checkout, 'exact_button', return_value=button), \
                    patch.object(checkout.time, 'sleep'), \
                    patch.object(checkout.time, 'monotonic', side_effect=[0, 0, 1801]):
                checkout.paused_checkout(driver, {}, result, output)
        return result, button

    def order_command(self, **changes):
        command = dict(action='create_unpaid_order', approved_total=2480, approved_quantity=1,
                       payment_method='ATM', selector='button', expected_text='前往付款')
        command.update(changes)
        return command

    def test_changed_page_is_rejected(self):
        result, button = self.run_command(self.order_command(expected_url='https://ticketplus.com.tw/old'))
        self.assertIn('Page changed', result['action_error'])
        button.click.assert_not_called()

    def test_more_than_one_ticket_is_rejected(self):
        result, button = self.run_command(self.order_command(approved_quantity=2))
        self.assertIn('limited to one', result['action_error'])
        button.click.assert_not_called()

    def test_higher_amount_is_rejected(self):
        result, button = self.run_command(self.order_command(approved_total=3080))
        self.assertIn('limited to one', result['action_error'])
        button.click.assert_not_called()

    def test_credit_card_method_is_rejected(self):
        result, button = self.run_command(self.order_command(payment_method='credit_card'))
        self.assertIn('unpaid ATM', result['action_error'])
        button.click.assert_not_called()

    def test_payment_button_is_rejected_even_for_atm_order(self):
        result, button = self.run_command(self.order_command(expected_text='確認付款'))
        self.assertIn('ATM account creation button', result['action_error'])
        button.click.assert_not_called()

    def test_order_can_only_be_submitted_from_confirmation_page(self):
        result, button = self.run_command(self.order_command(), path='/activity/event')
        self.assertIn('checkout page', result['action_error'])
        button.click.assert_not_called()

    def test_missing_unpaid_status_cannot_be_marked_successful(self):
        result, button = self.run_command(dict(action='record_unpaid_order'),
                                          result={'order_submission_attempted': True})
        self.assertFalse(result['unpaid_order_created'])
        self.assertIn('No unpaid-order status', result['action_error'])
        button.click.assert_not_called()

    def test_submit_attempt_does_not_itself_claim_order_success(self):
        result, button = self.run_command(self.order_command())
        button.click.assert_called_once()
        self.assertTrue(result['order_submission_attempted'])
        self.assertFalse(result['unpaid_order_created'])

    def test_atm_must_actually_be_selected(self):
        result, button = self.run_command(self.order_command(), atm_selected=False)
        self.assertIn('ATM must be selected', result['action_error'])
        button.click.assert_not_called()

    def test_selected_credit_card_is_rejected(self):
        result, button = self.run_command(self.order_command(), card_selected=True)
        self.assertIn('credit card must be unselected', result['action_error'])
        button.click.assert_not_called()

    def test_changed_displayed_total_is_rejected(self):
        result, button = self.run_command(self.order_command(), body='夢境邊界 ATM 共 1 張\n總金額\nNT. 3,080')
        self.assertIn('Review the current payment', result['action_error'])
        button.click.assert_not_called()

    def test_confirm_seat_uses_current_case_sensitive_route(self):
        result, button = self.run_command(dict(action='confirm_seat'), path='/confirmSeat/event/session')
        self.assertNotIn('action_error', result)
        button.click.assert_called_once()

    def test_contact_step_requires_approved_terms(self):
        result, button = self.run_command(dict(action='confirm_contact'), path='/confirm/event/session')
        self.assertIn('approved terms', result['action_error'])
        button.click.assert_not_called()

    def test_observed_atm_confirmation_records_unpaid_success(self):
        result, button = self.run_command(
            dict(action='record_unpaid_order'),
            title='訂單成立 | Ticket Plus遠大售票系統',
            body='您的訂單已成立！請在期限前完成繳款程序\nATM 虛擬帳號\n付款金額 NT.2,480',
            result={'order_submission_attempted': True})
        self.assertTrue(result['unpaid_order_created'])
        self.assertTrue(result['order_submitted'])
        self.assertFalse(result['payment_submitted'])
        button.click.assert_not_called()


if __name__ == '__main__':
    unittest.main()
