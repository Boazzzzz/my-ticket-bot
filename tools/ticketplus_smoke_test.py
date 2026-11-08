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
    result = {'activity_url': args.url, 'status': 'not_completed', 'date_selected': False,
              'ticket_number_assigned': False, 'captcha_tested': False,
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
                result['status'] = 'order_page_reached'
                state = {'fail_list': [], 'is_popup_confirm': False}
                bot.ticketplus_order(driver, config, None, None, state)
                counts = [element.text for element in driver.find_elements(bot.By.CSS_SELECTOR, 'div.count-button > div')]
                result['ticket_counts'] = counts
                result['ticket_number_assigned'] = '1' in counts
                result['status'] = 'quantity_selected' if result['ticket_number_assigned'] else 'quantity_selection_failed'
                checkpoint('ticket-selection')
                break
            if time.monotonic() - last_action >= 10 and '/activity/' in url:
                selected = bot.ticketplus_date_auto_select(driver, config)
                result['date_selected'] = result['date_selected'] or selected
                date_attempts += 1
                result['date_selector_count'] = len(driver.find_elements(bot.By.CSS_SELECTOR, 'div#buyTicket > div.sesstion-item > div.row'))
                if date_attempts == 1:
                    checkpoint('activity-page')
                if date_attempts >= 3 and not result['date_selector_count']:
                    result['status'] = 'activity_selectors_not_found'
                    checkpoint('activity-selectors-not-found')
                    break
                last_action = time.monotonic()
            time.sleep(2)
        else:
            result['status'] = 'login_wait_expired' if login_deadline is not None else 'timeout'
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
