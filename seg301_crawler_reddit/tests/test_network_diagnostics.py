import io
import json
import socket
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from reddit_app.network import diagnose_network
from reddit_app.main import main


class NetworkDiagnosticTests(unittest.TestCase):
    def test_identifies_proxy_hostname_failure_without_leaking_credentials(self):
        def resolve(host, port, *, type):
            if host == "missing-proxy.invalid":
                raise socket.gaierror(socket.EAI_NONAME, "unavailable")
            return [object()]
        with patch("urllib.request.getproxies", return_value={"https": "http://user:secret@missing-proxy.invalid:8080"}), \
             patch("urllib.request.proxy_bypass", return_value=False), patch("socket.getaddrinfo", resolve):
            result = diagnose_network()
        self.assertEqual(result["assessment"], "proxy_dns_failure")
        self.assertEqual(result["proxy"]["hostname"], "missing-proxy.invalid")
        self.assertNotIn("secret", json.dumps(result))
        self.assertNotIn("http://user", json.dumps(result))

    def test_identifies_general_dns_failure(self):
        with patch("urllib.request.getproxies", return_value={}), \
             patch("socket.getaddrinfo", side_effect=socket.gaierror(socket.EAI_NONAME, "unavailable")):
            result = diagnose_network()
        self.assertEqual(result["assessment"], "general_dns_failure")
        self.assertEqual(len(result["dns_checks"]), 2)

    def test_distinguishes_reddit_only_dns_failure(self):
        def resolve(host, port, *, type):
            if host == "www.reddit.com":
                raise socket.gaierror(socket.EAI_NONAME, "unavailable")
            return [object()]
        with patch("urllib.request.getproxies", return_value={}), patch("socket.getaddrinfo", resolve):
            self.assertEqual(diagnose_network()["assessment"], "reddit_dns_failure")

    def test_no_proxy_configuration_is_respected(self):
        with patch("urllib.request.getproxies", return_value={"https": "http://proxy.invalid:8080"}), \
             patch("urllib.request.proxy_bypass", return_value=True), \
             patch("socket.getaddrinfo", return_value=[object()]) as resolve:
            result = diagnose_network()
        self.assertEqual(result["assessment"], "dns_ok")
        self.assertFalse(result["proxy"]["active_for_reddit"])
        self.assertEqual(resolve.call_count, 2)

    def test_diagnose_cli_works_without_api_credentials(self):
        with patch.dict("os.environ", {}, clear=True), patch("urllib.request.getproxies", return_value={}), \
             patch("socket.getaddrinfo", return_value=[object()]), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["diagnose"]), 0)
        self.assertEqual(json.loads(output.getvalue())["assessment"], "dns_ok")


if __name__ == "__main__":
    unittest.main()
