"""Thin client for the Bellhaven CRM sandbox.

The API documents no request bodies, so write payloads mirror the field names
returned by GET. Every write goes through _write(), which honours dry_run and
records a call log the review app can display.
"""

import time

import requests

import config


class CrmError(RuntimeError):
    pass


PARENT_SHELL_MARKER = "(Parent Account)"


class Crm:
    def __init__(self, base=None, token=None, dry_run=False):
        self.base = (base or config.CRM_BASE).rstrip("/")
        token = token if token is not None else config.CRM_TOKEN
        if not token:
            raise CrmError(
                "CRM_TOKEN is not set. Copy .env.example to .env and add your token."
            )
        self.dry_run = dry_run
        self.log = []
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": "Bearer " + token, "Accept": "application/json"}
        )

    def _request(self, method, path, **kwargs):
        url = self.base + path
        last = None
        for attempt in range(4):
            try:
                response = self.session.request(method, url, timeout=20, **kwargs)
            except (requests.ConnectionError, requests.Timeout) as exc:
                last = exc
            else:
                if response.status_code < 400:
                    return response.json() if response.content else {}
                if response.status_code < 500:
                    raise CrmError(
                        "%s %s -> %s: %s"
                        % (method, path, response.status_code, response.text[:400])
                    )
                last = CrmError(
                    "%s %s -> %s" % (method, path, response.status_code)
                )
            if attempt < 3:
                time.sleep(1.5 * (attempt + 1))
        raise CrmError("%s %s failed after retries: %s" % (method, path, last))

    def _write(self, method, path, payload):
        self.log.append({"method": method, "path": path, "body": payload})
        if self.dry_run:
            return {"dry_run": True, "method": method, "path": path, "body": payload}
        return self._request(method, path, json=payload)

    def list_accounts(self):
        """Every account, following pagination."""
        rows, page = [], 1
        while True:
            data = self._request(
                "GET", "/accounts", params={"page": page, "page_size": 200}
            )
            batch = data.get("data") or []
            rows.extend(batch)
            total = data.get("total", len(rows))
            if not batch or len(rows) >= total:
                return rows
            page += 1

    def search_accounts(self, street="", zip_code="", parent_id=""):
        """Narrow account lookup, used to make account creation recoverable."""
        params = {"page": 1, "page_size": 50}
        if street:
            params["street"] = street
        if zip_code:
            params["zip"] = zip_code
        if parent_id:
            params["parent_id"] = parent_id
        data = self._request("GET", "/accounts", params=params)
        return data.get("data") or []

    def get_account(self, account_id):
        return self._request("GET", "/accounts/" + account_id)

    def update_account(self, account_id, fields):
        return self._write("PATCH", "/accounts/" + account_id, fields)

    def create_account(self, fields):
        return self._write("POST", "/accounts", fields)


def is_facility(account):
    """Parent shells carry no address and must stay out of address indexes."""
    if PARENT_SHELL_MARKER in (account.get("name") or ""):
        return False
    return bool((account.get("billing_street") or "").strip())
