"""Exercise the existing TicketPlus selectors without submitting an order.

Run with the project's Python environment:
    python tools/ticketplus_smoke_test.py --url https://ticketplus.com.tw/activity/EVENT_ID

Screenshots and results stay in a temporary directory, outside Git.
"""

import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import chrome_tixcraft as bot


RESTRICTED_TICKET_WORDS = ('身障', '愛心', '陪同', '會員限定', '序號', '優先購')


class TicketSelectionTracker:
    """Observe the specific ticket container operated on by the production helper."""

    def __init__(self, driver, assign):
        self.driver = driver
        self.assign = assign
        self.target = None

    def __call__(self, target, config):
        assigned = self.assign(target, config)
        # A page-wide fallback cannot identify which ticket type was chosen.
        if assigned and target is not self.driver:
            self.target = target
        return assigned

    def snapshot(self):
        if self.target is None:
            return None
        try:
            counter = self.target.find_element(bot.By.CSS_SELECTOR, 'div.count-button > div')
            label = self.target.text.strip()
            if (counter.is_displayed() and counter.text.strip() == '1' and label
                    and not any(word in label for word in RESTRICTED_TICKET_WORDS)):
                return {'ticket_type': label, 'quantity': 1}
        except bot.WebDriverException:
            # Vue may replace the row while rendering; let the caller retry.
            pass
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--login-wait-seconds', type=int, default=0)
    args = parser.parse_args()
    parsed = urlsplit(args.url)
    if (parsed.scheme != 'https' or parsed.netloc != 'ticketplus.com.tw'
            or not parsed.path.startswith('/activity/') or parsed.query or parsed.fragment):
        parser.error('--url must be a public TicketPlus activity URL')
    if not 0 <= args.login_wait_seconds <= 1800:
        parser.error('--login-wait-seconds must be between 0 and 1800')

    output = Path(tempfile.mkdtemp(prefix='ticketplus-smoke-'))
    print('OUTPUT_DIR', output, flush=True)
    config = copy.deepcopy(json.loads((ROOT / 'settings.json').read_text()))
    config.update(homepage=args.url, browser='chrome', webdriver_type='selenium', ticket_number=1)
    advanced = config['advanced']
    for key in advanced:
        if any(part in key for part in ('account', 'password', 'sid', 'ibonqware')):
            advanced[key] = ''
    advanced.update(headless=False, verbose=False, chrome_extension=False,
                    auto_guess_options=False, user_guess_string='',
                    proxy_server_port='', auto_reload_page_interval=5)
    advanced['play_sound'].update(ticket=False, order=False)
    config['ocr_captcha'].update(enable=False, force_submit=False)
    config['date_auto_select'].update(enable=True, date_keyword='', mode='from top to bottom')
    config['area_auto_select'].update(enable=True, area_keyword='', mode='from top to bottom')
    config['tixcraft']['auto_reload_coming_soon_page'] = False
    restricted = ','.join(json.dumps(word, ensure_ascii=False) for word in RESTRICTED_TICKET_WORDS)
    config['keyword_exclude'] = ','.join(filter(None, (config.get('keyword_exclude', ''), restricted)))

    original_options = bot.get_chrome_options

    def secure_test_options(*parameters):
        options = original_options(*parameters)
        for argument in list(options.arguments):
            if argument in ('--no-sandbox', '--disable-client-side-phishing-detection') or argument.startswith('--disable-features=IsolateOrigins'):
                options.arguments.remove(argument)
        prefs = dict(options.experimental_options.get('prefs', {}))
        prefs.pop('safebrowsing.enabled', None)
        prefs.pop('safebrowsing.enhanced', None)
        options.add_experimental_option('prefs', prefs)
        return options

    bot.get_chrome_options = secure_test_options
    # Keep event questions, CAPTCHA, agreements and confirmation out of this test.
    bot.ticketplus_order_exclusive_code = lambda *_: (False, [], False)
    bot.ticketplus_ticket_agree = lambda *_: False
    bot.ticketplus_confirm = lambda *_: None

    driver = bot.get_driver_by_config(config)
    if driver is None:
        raise RuntimeError('Could not start the project browser')
    tracker = TicketSelectionTracker(driver, bot.ticketplus_assign_ticket_number)
    bot.ticketplus_assign_ticket_number = tracker
    result = {'activity_url': args.url, 'status': 'not_completed', 'date_selected': False,
              'order_page_reached': False, 'ticket_number_assigned': False, 'captcha_tested': False,
              'order_submitted': False}

    def checkpoint(name):
        driver.save_screenshot(str(output / (name + '.png')))
        (output / (name + '.txt')).write_text(driver.find_element(bot.By.TAG_NAME, 'body').text)
        (output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print('CHECKPOINT', json.dumps(result, ensure_ascii=False), flush=True)

    stage_deadline = time.monotonic() + 120
    login_deadline = None
    last_action = 0
    last_url = ''
    date_attempts = 0
    try:
        while time.monotonic() < (login_deadline if login_deadline is not None else stage_deadline):
            url = driver.current_url
            if url != last_url:
                print('PAGE', url.split('?')[0], flush=True)
                last_url = url
                last_action = 0
                stage_deadline = time.monotonic() + 120
            if '/confirm/' in url or '/confirmseat/' in url:
                raise RuntimeError('Unexpected confirmation page; stopping')
            password_fields = driver.find_elements(bot.By.CSS_SELECTOR, 'input[type="password"]')
            needs_login = any(field.is_displayed() for field in password_fields)
            if needs_login:
                if login_deadline is None:
                    result['status'] = 'needs_manual_login'
                    checkpoint('login-required')
                    print('ACTION_REQUIRED Log in manually in the test Chrome window.', flush=True)
                    if not args.login_wait_seconds:
                        break
                    login_deadline = time.monotonic() + args.login_wait_seconds
                if time.monotonic() > login_deadline:
                    result['status'] = 'login_wait_expired'
                    break
                time.sleep(2)
                continue
            if login_deadline is not None:
                login_deadline = None
                stage_deadline = time.monotonic() + 120
                last_action = 0
            if '/order/' in url:
                if not result['order_page_reached']:
                    result.update(status='order_page_reached', order_page_reached=True)
                    checkpoint('order-page')
                state = {'fail_list': [], 'is_popup_confirm': False}
                bot.ticketplus_order(driver, config, None, None, state)
                selection = tracker.snapshot()
                if selection is not None:
                    if driver.current_url != url:
                        raise RuntimeError('Page changed during ticket selection; stopping')
                    result.update(status='quantity_selected', ticket_number_assigned=True,
                                  selected_ticket=selection)
                    driver.execute_script('arguments[0].scrollIntoView({block: "center"});', tracker.target)
                    checkpoint('ticket-selection')
                    break
                time.sleep(2)
                continue
            if time.monotonic() - last_action >= 10 and '/activity/' in url:
                selected = bot.ticketplus_date_auto_select(driver, config)
                result['date_selected'] = result['date_selected'] or selected
                date_attempts += 1
                result['date_selector_count'] = len(driver.find_elements(bot.By.CSS_SELECTOR, bot.CONST_TICKETPLUS_DATE_ROW_SELECTOR))
                if date_attempts == 1:
                    checkpoint('activity-page')
                if date_attempts >= 3 and not result['date_selector_count']:
                    result['status'] = 'activity_selectors_not_found'
                    checkpoint('activity-selectors-not-found')
                    break
                last_action = time.monotonic()
            time.sleep(2)
        else:
            if login_deadline is not None:
                result['status'] = 'login_wait_expired'
            elif result['order_page_reached']:
                result['status'] = 'quantity_selection_failed'
            else:
                result['status'] = 'timeout'
            checkpoint('timeout')
    except Exception as exc:
        result.update(status='error', error_type=type(exc).__name__)
        checkpoint('error')
        raise
    finally:
        (output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        driver.quit()
        print('FINISHED', json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result['ticket_number_assigned'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
