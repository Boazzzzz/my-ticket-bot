"""Regression coverage for process startup and refresh races; no ticket site requests."""
import json
import os
from pathlib import Path
import queue
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chrome_tixcraft as bot
import settings
import util
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, WebDriverException


class LaunchTests(unittest.TestCase):
    def child(self, source, config=None, **kwargs):
        events = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'chrome_tixcraft.py').write_text(source)
            (root / 'settings.json').write_text(json.dumps(config or {}))
            with patch.object(util, '__file__', str(root / 'util.py')):
                process = util.launch_maxbot(on_status=events.append, **kwargs)
            log_path = Path(events[0]['log_path'])
            log = log_path.read_text()
            mode = log_path.stat().st_mode & 0o777
            log_path.unlink()
        return process, events, log, mode

    def test_child_ready_and_clean_exit(self):
        process, events, log, mode = self.child("print('MAXBOT_STATUS:ready', flush=True)\nprint('running')")
        self.assertEqual([e['status'] for e in events], ['starting', 'ready', 'stopped'])
        self.assertEqual(process.returncode, 0)
        self.assertIn('running', log)
        if os.name != 'nt': self.assertEqual(mode, 0o600)

    def test_missing_dependency_reported_to_gui(self):
        _, events, log, _ = self.child('import missing_maxbot_test_module')
        self.assertEqual([e['status'] for e in events], ['starting', 'error'])
        self.assertIn('ModuleNotFoundError', log)

    def test_zero_exit_before_browser_ready_is_failure(self):
        _, events, _, _ = self.child('print("driver unavailable")')
        self.assertEqual(events[-1]['status'], 'error')

    def test_crash_after_ready_is_failure(self):
        _, events, log, _ = self.child("print('MAXBOT_STATUS:ready', flush=True)\nraise RuntimeError('test crash')")
        self.assertEqual([e['status'] for e in events], ['starting', 'ready', 'error'])
        self.assertIn('test crash', log)

    def test_error_marker_with_zero_exit_is_failure(self):
        _, events, _, _ = self.child("print('MAXBOT_STATUS:ready')\nprint('MAXBOT_STATUS:error')")
        self.assertEqual(events[-1]['status'], 'error')

    def test_frozen_launch_preserves_argument_boundaries(self):
        with patch.object(util.sys, 'frozen', True, create=True), patch.object(util.subprocess, 'Popen') as popen:
            util.launch_maxbot(filename='path with spaces.json', window_size='1200,800,0')
        command = popen.call_args.args[0]
        self.assertIn('--input=path with spaces.json', command)
        self.assertIn('--window_size=1200,800,0', command)
        self.assertNotIn('shell', popen.call_args.kwargs)

    def test_credentials_are_redacted(self):
        config = {'advanced': {'ticketplus_account': 'test-account', 'ticketplus_password_plaintext': 'test-secret'}}
        _, _, log, _ = self.child("print('test-account test-secret cli-secret')\nprint(\"{'ticketplus_password': 'encoded-value'}\")", config,
                                   kktix_password='cli-secret')
        for secret in ('test-account', 'test-secret', 'cli-secret', 'encoded-value'):
            self.assertNotIn(secret, log)

    def test_popen_failure_reports_error(self):
        events = []
        with patch.object(util.subprocess, 'Popen', side_effect=FileNotFoundError):
            self.assertIsNone(util.launch_maxbot(on_status=events.append))
        self.assertEqual(events[-1]['status'], 'error')
        Path(events[0]['log_path']).unlink()

    def test_network_timeout_default_and_override(self):
        for initial, expected in (({}, '10'), ({'SE_TIMEOUT': '45'}, '45')):
            with self.subTest(initial=initial), patch.dict(os.environ, initial, clear=True), patch.object(util.subprocess, 'Popen') as popen:
                util.launch_maxbot()
                self.assertEqual(popen.call_args.kwargs['env']['SE_TIMEOUT'], expected)
                self.assertEqual(popen.call_args.args[0][0], sys.executable)


class GuiLaunchTests(unittest.TestCase):
    def setUp(self):
        self.patches = []
        for name, value in dict(btn_run=Mock(), bot_launch_status=Mock(), root=Mock(),
                                bot_launch_events=queue.Queue(), bot_launch_pending=False,
                                bot_launch_id=10).items():
            p = patch.object(settings, name, value, create=True)
            p.start(); self.patches.append(p)
        self.addCleanup(lambda: [p.stop() for p in reversed(self.patches)])

    def test_repeat_click_while_starting_does_not_spawn_twice(self):
        with patch.object(settings, 'btn_save_act', return_value=True), patch.object(settings, 'launch_maxbot') as launch:
            settings.btn_run_clicked(); settings.btn_run_clicked()
        launch.assert_called_once()
        self.assertTrue(settings.bot_launch_pending)
        settings.btn_run.config.assert_called_with(state='disabled')

    def test_failure_is_visible_and_allows_retry(self):
        settings.bot_launch_pending = True
        settings.bot_launch_events.put({'launch_id':10, 'status':'error', 'log_path':'/tmp/test.log'})
        settings.poll_bot_launch_events()
        self.assertFalse(settings.bot_launch_pending)
        self.assertIn('/tmp/test.log', settings.bot_launch_status.set.call_args.args[0])
        settings.btn_run.config.assert_called_with(state='normal')

    def test_old_process_exit_cannot_unlock_new_launch(self):
        settings.bot_launch_pending = True
        settings.bot_launch_events.put({'launch_id':9, 'status':'stopped'})
        settings.poll_bot_launch_events()
        self.assertTrue(settings.bot_launch_pending)
        settings.btn_run.config.assert_not_called()

    def test_invalid_number_does_not_leave_button_disabled(self):
        with patch.object(settings, 'btn_save_act', side_effect=ValueError):
            settings.btn_run_clicked()
        self.assertFalse(settings.bot_launch_pending)
        settings.btn_run.config.assert_called_with(state='normal')


class DriverStartupTests(unittest.TestCase):
    def setUp(self):
        service = patch.object(bot, "Service")
        service.start()
        self.addCleanup(service.stop)

    def test_manager_success_never_uses_legacy_installer(self):
        expected = Mock()
        with tempfile.TemporaryDirectory() as directory, patch.object(bot.util, 'get_app_root', return_value=directory), \
             patch.object(bot, 'get_chrome_options'), patch.object(bot.webdriver, 'Chrome', return_value=expected) as chrome, \
             patch.object(bot.chromedriver_autoinstaller_max, 'install') as legacy:
            self.assertIs(bot.load_chromdriver_normal({}, 'selenium'), expected)
        self.assertEqual(chrome.call_count, 1)
        legacy.assert_not_called()

    def test_manager_failure_uses_existing_local_driver(self):
        expected = Mock()
        with tempfile.TemporaryDirectory() as directory, patch.object(bot.util, 'get_app_root', return_value=directory), \
             patch.object(bot, 'get_chrome_options'), patch.object(bot, 'get_chromedriver_path', return_value=__file__), \
             patch.object(bot.webdriver, 'Chrome', side_effect=[WebDriverException('network'), expected]) as chrome:
            self.assertIs(bot.load_chromdriver_normal({}, 'selenium'), expected)
            self.assertEqual(chrome.call_count, 2)

    def test_no_driver_failure_propagates(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(bot.util, 'get_app_root', return_value=directory), \
             patch.object(bot, 'get_chrome_options'), patch.object(bot.webdriver, 'Chrome', side_effect=WebDriverException('network')):
            with self.assertRaises(WebDriverException): bot.load_chromdriver_normal({}, 'selenium')


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.driver = Mock()
        self.driver.current_url = 'https://ticketplus.com.tw/order/test/session'
        self.config = {'advanced': {'auto_reload_page_interval': 0.1},
                       'tixcraft': {'auto_reload_coming_soon_page': True}}

    def test_subsecond_refresh_burst_is_throttled(self):
        with patch.object(bot.time, 'monotonic', side_effect=[0, 0.1, 0.9, 1]):
            self.assertEqual([bot.ticketplus_refresh(self.driver, self.config) for _ in range(4)], [True, False, False, True])
        self.assertEqual(self.driver.refresh.call_count, 2)

    def test_longer_user_interval_is_preserved(self):
        self.config['advanced']['auto_reload_page_interval'] = 5
        with patch.object(bot.time, 'monotonic', side_effect=[0, 1, 4.9, 5]):
            self.assertEqual([bot.ticketplus_refresh(self.driver, self.config) for _ in range(4)], [True, False, False, True])

    def test_failed_refresh_cannot_spin(self):
        self.driver.refresh.side_effect = TimeoutException()
        with patch.object(bot.time, 'monotonic', side_effect=[0, 0.1]):
            with self.assertRaises(TimeoutException): bot.ticketplus_refresh(self.driver, self.config)
            self.assertFalse(bot.ticketplus_refresh(self.driver, self.config))
        self.driver.refresh.assert_called_once()

    def test_inventory_checks_respect_disabled_setting(self):
        self.config['tixcraft']['auto_reload_coming_soon_page'] = False
        self.assertFalse(bot.ticketplus_order_auto_reload_coming_soon(self.driver, self.config))
        self.driver.get_log.assert_not_called()
        self.driver.execute_script.assert_not_called()

    def test_inventory_query_not_repeated_each_tick(self):
        url = 'https://apis.ticketplus.com.tw/config/api/get?productId=test'
        self.driver.execute_script.return_value = 'checking'
        with patch.object(bot, 'get_performance_log', return_value=[url]) as log, \
             patch.object(bot.time, 'monotonic', side_effect=[0, 0.05, 0.1, 0.9]):
            for _ in range(4): self.assertTrue(bot.ticketplus_order_auto_reload_coming_soon(self.driver, self.config))
        log.assert_called_once()
        self.driver.execute_script.assert_called_once()
        self.driver.set_script_timeout.assert_not_called()

    def test_pending_inventory_uses_throttled_python_refresh(self):
        url = 'https://apis.ticketplus.com.tw/config/api/get?ticketAreaId=test'
        self.driver.execute_script.return_value = 'pending'
        with patch.object(bot, 'get_performance_log', return_value=[url]), patch.object(bot.time, 'monotonic', return_value=0):
            self.assertTrue(bot.ticketplus_order_auto_reload_coming_soon(self.driver, self.config))
            self.assertFalse(bot.ticketplus_refresh(self.driver, self.config))
        self.driver.refresh.assert_called_once()

    def test_transient_navigation_error_is_retried_but_bounded(self):
        with patch.object(bot, 'ticketplus_main', side_effect=StaleElementReferenceException()), patch.object(bot.time, 'sleep'):
            for _ in range(4): bot.ticketplus_run_iteration(self.driver, '', {}, None, None)
            with self.assertRaises(StaleElementReferenceException): bot.ticketplus_run_iteration(self.driver, '', {}, None, None)

    def test_success_resets_transient_error_count(self):
        with patch.object(bot, 'ticketplus_main', side_effect=[TimeoutException(), None, TimeoutException()]), patch.object(bot.time, 'sleep'):
            for _ in range(3): bot.ticketplus_run_iteration(self.driver, '', {}, None, None)
        self.assertEqual(bot.ticketplus_runtime(self.driver)['transient_errors'], 1)

    def test_real_session_crash_is_not_hidden(self):
        with patch.object(bot, 'ticketplus_main', side_effect=WebDriverException('invalid session id')):
            with self.assertRaises(WebDriverException): bot.ticketplus_run_iteration(self.driver, '', {}, None, None)


class LocalBrowserRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        options = bot.webdriver.ChromeOptions()
        options.add_argument('--headless=new')
        cls.driver = bot.webdriver.Chrome(options=options)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def setUp(self):
        self.driver.__dict__.pop('_maxbot_ticketplus_runtime', None)
        self.driver.get('data:text/html,<title>local-refresh-test</title><p>local only</p>')
        self.config = {'advanced': {'auto_reload_page_interval': 0.1},
                       'tixcraft': {'auto_reload_coming_soon_page': True}}
        self.url = 'https://apis.ticketplus.com.tw/config/api/get?productId=local-test'

    def stub_inventory(self, status):
        self.driver.execute_script("""
window.fetchCount = 0;
window.fetch = () => {
  window.fetchCount++;
  return Promise.resolve({ok: true, json: () => Promise.resolve({result: {product: [{status: arguments[0]}]}})});
};
""", status)

    def test_inventory_fetch_runs_once_per_document_without_changing_script_timeout(self):
        self.stub_inventory('on_sale')
        timeout = self.driver.timeouts.script
        with patch.object(bot, 'get_performance_log', return_value=[self.url]), patch.object(bot.time, 'monotonic', return_value=0):
            self.assertTrue(bot.ticketplus_order_auto_reload_coming_soon(self.driver, self.config))
        bot.WebDriverWait(self.driver, 5).until(lambda d: d.execute_script(
            'return window.__maxbotTicketplusInventory.status') == 'ready')
        with patch.object(bot, 'get_performance_log', return_value=[]), patch.object(bot.time, 'monotonic', return_value=2):
            self.assertFalse(bot.ticketplus_order_auto_reload_coming_soon(self.driver, self.config))
        self.assertEqual(self.driver.execute_script('return window.fetchCount'), 1)
        self.assertEqual(self.driver.timeouts.script, timeout)

    def test_pending_response_does_not_reload_from_javascript(self):
        self.stub_inventory('pending')
        with patch.object(bot, 'get_performance_log', return_value=[self.url]), patch.object(bot.time, 'monotonic', return_value=0):
            self.assertTrue(bot.ticketplus_order_auto_reload_coming_soon(self.driver, self.config))
        bot.WebDriverWait(self.driver, 5).until(lambda d: d.execute_script(
            'return window.__maxbotTicketplusInventory.status') == 'pending')
        self.assertEqual(self.driver.title, 'local-refresh-test')
        with patch.object(bot, 'get_performance_log', return_value=[]), patch.object(bot.time, 'monotonic', return_value=2), \
             patch.object(self.driver, 'refresh') as refresh:
            self.assertTrue(bot.ticketplus_order_auto_reload_coming_soon(self.driver, self.config))
            refresh.assert_called_once()

    def test_inventory_network_error_does_not_trigger_reload_loop(self):
        self.driver.execute_script("window.fetch = () => Promise.reject(new Error('test network failure'))")
        with patch.object(bot, 'get_performance_log', return_value=[self.url]), patch.object(bot.time, 'monotonic', return_value=0):
            self.assertTrue(bot.ticketplus_order_auto_reload_coming_soon(self.driver, self.config))
        bot.WebDriverWait(self.driver, 5).until(lambda d: d.execute_script(
            'return window.__maxbotTicketplusInventory.status') == 'error')
        with patch.object(bot, 'get_performance_log', return_value=[]), patch.object(bot.time, 'monotonic', return_value=2), \
             patch.object(self.driver, 'refresh') as refresh:
            self.assertFalse(bot.ticketplus_order_auto_reload_coming_soon(self.driver, self.config))
            refresh.assert_not_called()

    def test_real_refresh_burst_keeps_browser_usable(self):
        count = 0
        import time
        for _ in range(30):
            count += bot.ticketplus_refresh(self.driver, self.config)
            time.sleep(0.05)
        self.assertGreaterEqual(count, 1)
        self.assertLessEqual(count, 3)
        self.assertEqual(self.driver.title, 'local-refresh-test')


if __name__ == '__main__': unittest.main()
