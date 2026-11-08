"""Paused TicketPlus checkout diagnostics; never automatically pays or accepts terms.

Use the same --url and --login-wait-seconds arguments as ticketplus_smoke_test.py.
After selecting one ticket, the browser pauses. Each further action requires a
separate local request.json in OUTPUT_DIR and an exact expected_url. CAPTCHA and
agreement actions must only be requested after the user's action-time approval.
Keep all checkout artifacts local: they can contain account or order information.
"""

import argparse
import copy
import json
import re
import time
from urllib.parse import urlsplit

if __package__:
    from . import ticketplus_smoke_test as smoke
else:
    import ticketplus_smoke_test as smoke

bot = smoke.bot


def inspect_page(driver, result, output, name):
    driver.save_screenshot(str(output / (name + '.png')))
    text = driver.find_element(bot.By.TAG_NAME, 'body').text
    (output / (name + '.txt')).write_text(text)
    buttons = []
    for element in driver.find_elements(bot.By.CSS_SELECTOR, 'button'):
        if element.is_displayed():
            buttons.append({'text': element.text.strip(), 'class': element.get_attribute('class'),
                            'id': element.get_attribute('id'), 'enabled': element.is_enabled()})
    inputs = []
    for element in driver.find_elements(bot.By.CSS_SELECTOR, 'input'):
        if element.is_displayed():
            inputs.append({'type': element.get_attribute('type'), 'id': element.get_attribute('id'),
                           'placeholder': element.get_attribute('placeholder'),
                           'checked': element.is_selected()})
    state = {'url': driver.current_url, 'title': driver.title, 'buttons': buttons,
             'inputs': inputs, 'result': result}
    (output / 'checkout-state.json').write_text(json.dumps(state, ensure_ascii=False, indent=2))
    print('CHECKOUT_PAUSED', name, flush=True)


def exact_button(driver, selector, expected_text):
    matches = [element for element in driver.find_elements(bot.By.CSS_SELECTOR, selector)
               if element.is_displayed() and element.text.strip() == expected_text]
    if len(matches) != 1 or not matches[0].is_enabled():
        raise ValueError('Expected one enabled button with the approved text')
    return matches[0]


def paused_checkout(driver, config, result, output, approval=None):
    # Explicit per-run ticket limits; defaults preserve the original VERA test.
    approval = approval or {'price': 2480, 'label': '夢境邊界'}
    approved_price = approval['price']
    approved_label = approval['label']
    if type(approved_price) is not int or approved_price <= 0 or not approved_label.strip():
        raise ValueError('An explicit positive price and ticket label are required')
    activity_path = urlsplit(result.get('activity_url', '')).path.strip('/').split('/')
    activity_id = activity_path[-1] if len(activity_path) == 2 and activity_path[0] == 'activity' else None
    selected_ticket = result.get('selected_ticket', {})
    price = re.search(r'NT[.$\s]*([\d,]+)', selected_ticket.get('ticket_type', ''))
    if (selected_ticket.get('quantity') != 1 or price is None
            or int(price.group(1).replace(',', '')) != approved_price):
        raise ValueError('Checkout test requires the approved ticket price, quantity one')
    result.update(unpaid_order_created=False, payment_submitted=False,
                  checkout_status='awaiting_action', approved_ticket=approval.copy())
    inspect_page(driver, result, output, 'checkout-ready')
    model = None
    deadline = time.monotonic() + 1800
    sequence = 0
    while time.monotonic() < deadline:
        request_file = output / 'request.json'
        if not request_file.exists():
            time.sleep(1)
            continue
        command = json.loads(request_file.read_text())
        request_file.unlink()
        sequence += 1
        action = command.get('action')
        try:
            if action not in ('inspect', 'close') and command.get('expected_url') != driver.current_url:
                raise ValueError('Page changed; inspect and approve the current page first')
            if action not in ('inspect', 'close') and urlsplit(driver.current_url).netloc != 'ticketplus.com.tw':
                raise ValueError('Checkout actions are restricted to TicketPlus')
            if action not in ('inspect', 'close', 'record_unpaid_order') and activity_id:
                if activity_id not in urlsplit(driver.current_url).path.strip('/').split('/'):
                    raise ValueError('The page belongs to a different activity')
            if action == 'inspect':
                pass
            elif action == 'next_from_selection':
                if '/order/' not in driver.current_url:
                    raise ValueError('Next is only allowed on the ticket selection page')
                button = exact_button(driver, command['selector'], command['expected_text'])
                if re.search(r'付款|支付|結帳|pay|checkout', button.text, re.I):
                    raise ValueError('Payment action is outside this test')
                button.click()
            elif action in ('confirm_seat', 'confirm_contact'):
                expected_path = '/confirmSeat/' if action == 'confirm_seat' else '/confirm/'
                if expected_path not in driver.current_url:
                    raise ValueError('Expected the reviewed confirmation page')
                body = driver.find_element(bot.By.TAG_NAME, 'body').text
                if approved_label not in body or format(approved_price, ',') not in body:
                    raise ValueError('The approved ticket is not displayed')
                if action == 'confirm_contact' and not result.get('terms_checked'):
                    raise ValueError('Contact confirmation requires the approved terms first')
                exact_button(driver, 'button.nextBtn', '下一步').click()
            elif action == 'fill_captcha':
                # This command is issued only after explicit approval for the current CAPTCHA.
                if '/order/' not in driver.current_url:
                    raise ValueError('CAPTCHA test expects the ticket selection page')
                captcha_inputs = [element for element in driver.find_elements(
                    bot.By.CSS_SELECTOR, 'input[placeholder="請輸入驗證碼"]') if element.is_displayed()]
                if len(captcha_inputs) != 1 or captcha_inputs[0].get_attribute('value'):
                    raise ValueError('Expected one empty CAPTCHA field')
                if model is None:
                    model = bot.ddddocr.DdddOcr(show_ad=False, beta=config['ocr_captcha']['beta'])
                images = driver.find_elements(bot.By.CSS_SELECTOR, 'span.captcha-img')
                for image in images:
                    if image.is_displayed():
                        image.screenshot(str(output / 'captcha.png'))
                        break
                ocr_config = copy.deepcopy(config)
                ocr_config['ocr_captcha'].update(enable=True, force_submit=False)
                retry, previous, submitted = bot.ticketplus_auto_ocr(
                    driver, ocr_config, model, None, None)
                value = captcha_inputs[0].get_attribute('value')
                result.update(captcha_tested=True, captcha_input=value,
                              captcha_form_submitted=submitted)
                if submitted:
                    raise RuntimeError('OCR unexpectedly submitted a form')
            elif action == 'accept_terms':
                # Root must have shown these terms and obtained action-time confirmation.
                checkbox = driver.find_element(bot.By.CSS_SELECTOR, command['selector'])
                if checkbox.get_attribute('type') != 'checkbox':
                    raise ValueError('Expected the specifically approved agreement checkbox')
                bot.force_check_checkbox(driver, checkbox)
                result['terms_checked'] = checkbox.is_selected()
            elif action == 'create_unpaid_order':
                if '/checkout/' not in driver.current_url:
                    raise ValueError('Expected the reviewed checkout page')
                if command.get('approved_total') != approved_price or command.get('approved_quantity') != 1:
                    raise ValueError('This test is limited to one ticket at the approved price')
                if command.get('payment_method') != 'ATM':
                    raise ValueError('Only a reviewed unpaid ATM order is allowed')
                atm = driver.find_elements(bot.By.CSS_SELECTOR, 'input[type="radio"][value="ATM"]')
                cards = driver.find_elements(bot.By.CSS_SELECTOR, 'input[type="radio"][value="CC"]')
                if len(atm) != 1 or not atm[0].is_selected() or any(card.is_selected() for card in cards):
                    raise ValueError('ATM must be selected and credit card must be unselected')
                body = driver.find_element(bot.By.TAG_NAME, 'body').text
                total = re.search(r'總金額\s+NT\.\s*([\d,]+)(?:\s|$)', body)
                if ('ATM' not in body or approved_label not in body or '共 1 張' not in body
                        or total is None or int(total.group(1).replace(',', '')) != approved_price):
                    raise ValueError('Review the current payment method and amount first')
                button = exact_button(driver, command['selector'], command['expected_text'])
                if button.text.strip() != '前往付款':
                    raise ValueError('Expected the reviewed ATM account creation button')
                if re.search(r'立即付款|確認付款|信用卡|支付|pay now|charge', button.text, re.I):
                    raise ValueError('Payment action is outside this test')
                button.click()
                result['order_submission_attempted'] = True
            elif action == 'select_atm':
                if '/checkout/' not in driver.current_url:
                    raise ValueError('ATM selection requires the checkout page')
                for value in ('ibon', 'ATM'):
                    radios = driver.find_elements(bot.By.CSS_SELECTOR, 'input[type="radio"][value="%s"]' % value)
                    if len(radios) != 1:
                        raise ValueError('Expected one reviewed payment or collection option')
                    label = driver.find_element(bot.By.CSS_SELECTOR, 'label[for="%s"]' % radios[0].get_attribute('id'))
                    driver.execute_script('arguments[0].scrollIntoView({block: "center"});', label)
                    if not radios[0].is_selected():
                        label.click()
                    if not radios[0].is_selected():
                        raise ValueError('The requested option was not selected')
            elif action == 'record_unpaid_order':
                # Record only after the displayed order has been reviewed by the operator.
                if not result.get('order_submission_attempted'):
                    raise ValueError('An order submission must be observed first')
                body = driver.find_element(bot.By.TAG_NAME, 'body').text
                if not (driver.title.startswith('訂單成立') and '您的訂單已成立' in body
                        and 'ATM 虛擬帳號' in body and approved_label in body
                        and re.search(r'NT[.$\s]*' + re.escape(format(approved_price, ',')) + r'(?:\s|$)', body)
                        and '前完成繳款程序' in body):
                    raise ValueError('No unpaid-order status is displayed')
                result.update(unpaid_order_created=True, order_submitted=True,
                              checkout_status='unpaid_order_created')
            elif action == 'close':
                result['checkout_status'] = ('unpaid_order_created' if result['unpaid_order_created']
                                             else 'stopped_before_order')
                inspect_page(driver, result, output, 'checkout-finished')
                return
            else:
                raise ValueError('Unknown checkout test action')
            # Wait for the immediate UI update, then pause again; no next action is automatic.
            time.sleep(2)
            result['last_action'] = action
            result.pop('action_error', None)
        except Exception as exc:
            result['action_error'] = type(exc).__name__ + ': ' + str(exc).split('Stacktrace:')[0][:500]
            print('CHECKOUT_ACTION_ERROR', result['action_error'], flush=True)
        inspect_page(driver, result, output, 'checkout-%02d-%s' % (sequence, action))
    result['checkout_status'] = ('unpaid_order_created' if result['unpaid_order_created']
                                 else 'action_wait_expired')
    inspect_page(driver, result, output, 'checkout-wait-expired')


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--approved-price', type=int, default=2480)
    parser.add_argument('--ticket-label', default='夢境邊界')
    args, selection_args = parser.parse_known_args()
    if args.approved_price <= 0 or not args.ticket_label.strip():
        parser.error('provide a positive --approved-price and nonempty --ticket-label')
    approval = {'price': args.approved_price, 'label': args.ticket_label.strip()}
    checkout_result = {}

    def run_checkout(driver, config, result, output):
        paused_checkout(driver, config, result, output, approval=approval)
        checkout_result.update(result)

    selection_exit = smoke.main(on_selection=run_checkout,
                               area_keyword=json.dumps(str(args.approved_price)), argv=selection_args)
    return 0 if selection_exit == 0 and checkout_result.get('unpaid_order_created') else 1


if __name__ == '__main__':
    raise SystemExit(main())
