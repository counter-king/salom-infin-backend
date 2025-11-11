import base64
import datetime as dt
import hashlib
import hmac
import logging
import os
from typing import Dict, List, Optional, Tuple

import requests
from requests import Session

from utils.exception import SourceUnavailableError
from utils.utils import as_int, boolish

try:
    from urllib3.util.retry import Retry
except Exception:
    from requests.packages.urllib3.util.retry import Retry

HIK_BASE_URL = os.getenv('HIK_BASE_URL', "https://example.ihakv.net")
HIK_API_KEY = os.getenv('HIK_API_KEY')
HIK_API_SECRET = os.getenv('HIK_API_SECRET')
HIK_USER_ID = os.getenv('HIK_USER_ID')


class FaceIdClient:
    def __init__(
            self,
            base_url: str = HIK_BASE_URL,
            api_key: str = HIK_API_KEY,
            api_secret: str = HIK_API_SECRET,
            user_id: str = HIK_USER_ID,
            timeout: int = 15,
            *,
            max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.api_secret = api_secret
        self.user_id = user_id
        self.timeout = timeout

        self.session: Session = requests.Session()
        retry = Retry(
            total=max_retries,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["POST"]),
        )
        self.session.mount("https://", requests.adapters.HTTPAdapter(max_retries=retry))
        self.session.mount("http://", requests.adapters.HTTPAdapter(max_retries=retry))

    def _headers(self, endpoint: str) -> Dict[str, str]:
        accept = 'application/json'
        content_type = 'application/json;charset=UTF-8'
        method = 'POST'
        return {
            'Accept': accept,
            'Content-Type': content_type,
            'X-Ca-Key': self.api_key,
            'X-Ca-Signature': self._sign(method, accept, content_type, endpoint),
        }

    def _sign(self, method: str, accept: str, content_type: str, endpoint: str) -> str:
        text_to_sign = f"{method}\n{accept}\n{content_type}\n{endpoint}"
        return base64.b64encode(
            hmac.new(self.api_secret.encode(), text_to_sign.encode(), hashlib.sha256).digest()
        ).decode()

    def fetch_events(
            self,
            begin_time: str | dt.datetime,
            end_time: str | dt.datetime,
            page_no: int,
            page_size: int,
            org_index_codes: Optional[List[int]] = None,
            person_code: Optional[str] = None,
    ) -> Dict:

        query: Dict = {
            "beginTime": begin_time,
            "endTime": end_time,
            "sortInfo": {"sortField": 1, "sortType": 1},
        }
        if person_code:
            query["personCode"] = person_code
        if org_index_codes:
            query["orgIndexCode"] = org_index_codes

        payload = {
            "attendanceReportRequest": {
                "pageNo": int(page_no),
                "pageSize": int(page_size),
                "queryInfo": query,
            }
        }
        endpoint = "/artemis/api/attendance/v1/report"
        url = f"{self.base_url}{endpoint}"
        try:
            resp = self.session.post(
                url,
                headers=self._headers(endpoint),
                json=payload,
                timeout=self.timeout,
                verify=False,  # consider True + proper CA in prod
            )
            resp.raise_for_status()
            data = resp.json()
        except (requests.Timeout, requests.ConnectionError) as e:
            raise SourceUnavailableError(f"FACE-ID network error: {e}") from e
        except requests.HTTPError as e:
            status_code = resp.status_code
            if 500 <= status_code < 600 or status_code == 429:
                raise SourceUnavailableError(f"FACE-ID HTTP {status_code}") from e
            raise
        return data

    @staticmethod
    def _extract_report(resp_json: Dict) -> Tuple[List[Dict], bool, int, int]:
        """
        Top-level envelope:
          {"code":"0","msg":"Success","data":{
              "nextPage":"1"|"0"|true|false, "pageNo":"1"|1, "pageSize":"100"|100,
              "record":[...]}}

        Also tolerates endpoints that use 'list' and/or 'total'.
        Returns: (records, has_next, page_no, page_size)
        """
        code = str(resp_json.get("code", ""))
        if code != "0":
            raise ValueError(f"Vendor returned error code: {resp_json.get('code')}, msg={resp_json.get('msg')}")

        data = resp_json.get("data") or {}

        # Records may be under 'record' or 'list'
        records: List[Dict] = list(data.get("record") or data.get("list") or [])

        page_no = as_int(data.get("pageNo"), 1)
        page_size = as_int(data.get("pageSize"), len(records))

        # Prefer explicit paging flag if present
        if "nextPage" in data:
            has_next = boolish(data.get("nextPage"))
        else:
            # Fallback: derive from total/page math if provided
            total = data.get("total")
            if total is not None:
                has_next = (page_no * page_size) < as_int(total, len(records))
            else:
                # Last-resort heuristic: if we filled the page, assume maybe more
                has_next = (len(records) == page_size) and (page_size > 0)

        return records, has_next, page_no, page_size

    def _extract_people(self, resp_json: dict):
        """
        Expected shape:
          {"code":"0","msg":"Success","data":{
              "total": 4567,
              "pageNo": 1,
              "pageSize": 500,
              "list": [ {...}, ... ]
          }}
        Returns: (lst, total, page_no, page_size)
        """
        code = str(resp_json.get("code", ""))
        if code != "0":
            raise ValueError(f"Vendor error code={resp_json.get('code')} msg={resp_json.get('msg')}")
        data = resp_json.get("data") or {}

        # vendors sometimes use 'list', but be tolerant
        lst = list(data.get("list") or data.get("record") or data.get("records") or [])
        total = as_int(data.get("total"), len(lst))
        page_no = as_int(data.get("pageNo"), 1)
        page_size = as_int(data.get("pageSize"), len(lst))
        return lst, total, page_no, page_size

    def iter_report(self,
                    begin_time,
                    end_time, *,
                    page_size: int = 500,
                    org_index_codes: list[int] | None = None,
                    person_code: str | None = None):
        page_no = 1
        while True:
            raw = self.fetch_events(begin_time, end_time, page_no, page_size,
                                    org_index_codes=org_index_codes, person_code=person_code)
            recs, has_next, pno, psz = self._extract_report(raw)
            logging.info(f"[REPORT] page={pno} size={psz} got={len(recs)} has_next={has_next}")
            if not recs:
                break
            for r in recs:
                yield r
            if not has_next:
                break
            page_no += 1

    def get_people_page(self, *, page_no: int, page_size: int, query: Optional[Dict] = None) -> Dict:
        payload = {
            "pageNo": int(page_no),
            "pageSize": int(page_size)

        }
        endpoint = "/artemis/api/resource/v1/person/advance/personList"
        headers = self._headers(endpoint)
        url = f"{self.base_url}{endpoint}"
        resp = self.session.post(url, headers=headers, json=payload, timeout=self.timeout, verify=False)
        resp.raise_for_status()
        return resp.json()

    def iter_people(self, *, page_size: int = 500, query: Optional[Dict] = None):
        page_no = 1
        while True:
            raw = self.get_people_page(page_no=page_no, page_size=page_size, query=query)
            lst, total, pno, psz = self._extract_people(raw)
            logging.info(f"[PEOPLE] page={pno} size={psz} got={len(lst)} total={total}")
            if not lst:
                break
            for person in lst:
                yield person
            if pno * psz >= total:
                break
            page_no += 1
