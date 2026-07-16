"""Domestic KIS balance and cash-order integration."""

from __future__ import annotations

from typing import Literal

import requests

from backend import config, kis

OrderSide = Literal["buy", "sell"]
OrderType = Literal["limit", "market"]

_REAL_ORDER_REFUSAL = (
    "실계좌 주문이 차단되어 있습니다(KIS_ALLOW_REAL_ORDERS=true 설정 필요). "
    "모의투자(KIS_MOCK=true)를 사용하세요."
)


def _number(value: object) -> float:
    """Convert KIS string numbers without propagating bad data."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _integer(value: object) -> int:
    """Convert KIS integer-like string numbers defensively."""
    return int(_number(value))


def _price_text(price: float) -> str:
    """Format whole-won prices without a decimal suffix."""
    return format(price, "g")


def _account_parts() -> tuple[str, str] | None:
    """Return the account number and product code from common env formats."""
    raw = (config.KIS_ACCOUNT or "").strip()
    if not raw:
        return None
    if "-" in raw:
        account_no, product_code = raw.split("-", 1)
        return (account_no, product_code) if account_no and product_code else None
    digits = "".join(character for character in raw if character.isdigit())
    if len(digits) >= 10:
        return digits[:-2], digits[-2:]
    if len(digits) == 8:
        return digits, "01"
    return None


def _tr_id(real_tr_id: str) -> str:
    """Apply the verified T-to-V mapping for domestic TTTC TRs."""
    return f"V{real_tr_id[1:]}" if config.KIS_MOCK else real_tr_id


def _empty_balance(message: str) -> dict[str, object]:
    return {
        "positions": [],
        "cash": 0.0,
        "total_eval": 0.0,
        "total_purchase": 0.0,
        "pnl": 0.0,
        "message": message,
    }


def _order_failure(message: str) -> dict[str, object]:
    return {"ok": False, "order_no": None, "org_no": None, "message": message}


def _order_allowed() -> bool:
    return config.KIS_MOCK or config.KIS_ALLOW_REAL_ORDERS


def account() -> dict[str, object]:
    """Fetch all domestic positions and the account summary with TR paging."""
    parts = _account_parts()
    if parts is None:
        return _empty_balance("KIS 계좌번호가 설정되지 않았습니다.")
    headers = kis._headers(_tr_id("TTTC8434R"))
    if headers is None:
        return _empty_balance("KIS API 키 또는 토큰을 확인하세요.")

    account_no, product_code = parts
    fk100 = ""
    nk100 = ""
    positions: list[dict[str, object]] = []
    summary: dict[str, object] = {}
    try:
        for page in range(20):
            page_headers = dict(headers)
            if page:
                page_headers["tr_cont"] = "N"
            response = requests.get(
                f"{kis.base_url()}/uapi/domestic-stock/v1/trading/inquire-balance",
                headers=page_headers,
                params={
                    "CANO": account_no,
                    "ACNT_PRDT_CD": product_code,
                    "AFHR_FLPR_YN": "N",
                    "OFL_YN": "",
                    "INQR_DVSN": "02",
                    "UNPR_DVSN": "01",
                    "FUND_STTL_ICLD_YN": "N",
                    "FNCG_AMT_AUTO_RDPT_YN": "N",
                    "PRCS_DVSN": "01",
                    "CTX_AREA_FK100": fk100,
                    "CTX_AREA_NK100": nk100,
                },
                timeout=10,
            )
            response.raise_for_status()
            data: object = response.json()
            if not isinstance(data, dict):
                return _empty_balance("KIS 잔고 응답 형식이 올바르지 않습니다.")
            if data.get("rt_cd") != "0":
                message = data.get("msg1")
                return _empty_balance(
                    message if isinstance(message, str) else "KIS 잔고 조회에 실패했습니다."
                )

            output1 = data.get("output1")
            if isinstance(output1, list):
                for row in output1:
                    if not isinstance(row, dict):
                        continue
                    qty = _integer(row.get("hldg_qty"))
                    if qty <= 0:
                        continue
                    positions.append(
                        {
                            "symbol": str(row.get("pdno", "")),
                            "name": str(row.get("prdt_name", "")),
                            "qty": qty,
                            "avg_price": _number(row.get("pchs_avg_pric")),
                            "current_price": _number(row.get("prpr")),
                            "eval_amount": _number(row.get("evlu_amt")),
                            "pnl": _number(row.get("evlu_pfls_amt")),
                            "pnl_pct": _number(row.get("evlu_pfls_rt")),
                        }
                    )

            output2 = data.get("output2")
            if isinstance(output2, list) and output2 and isinstance(output2[0], dict):
                summary = output2[0]

            fk_value = data.get("ctx_area_fk100")
            nk_value = data.get("ctx_area_nk100")
            fk100 = fk_value if isinstance(fk_value, str) else ""
            nk100 = nk_value if isinstance(nk_value, str) else ""
            if response.headers.get("tr_cont", "").upper() not in {"M", "F"}:
                break

        return {
            "positions": positions,
            "cash": _number(summary.get("dnca_tot_amt")),
            "total_eval": _number(summary.get("tot_evlu_amt")),
            "total_purchase": _number(summary.get("pchs_amt_smtl_amt")),
            "pnl": _number(summary.get("evlu_pfls_smtl_amt")),
            "message": "KIS 잔고를 조회했습니다.",
        }
    except Exception:  # noqa: BLE001 - optional broker calls must stay non-fatal
        return _empty_balance("KIS 잔고 조회에 실패했습니다.")


def order_cash(
    symbol: str,
    qty: int,
    price: float | None,
    order_type: OrderType,
    side: OrderSide = "buy",
) -> dict[str, object]:
    """Place a domestic cash buy or sell order."""
    if not _order_allowed():
        return _order_failure(_REAL_ORDER_REFUSAL)
    parts = _account_parts()
    if parts is None:
        return _order_failure("KIS 계좌번호가 설정되지 않았습니다.")
    if order_type == "limit" and price is None:
        return _order_failure("지정가 주문에는 가격이 필요합니다.")
    real_tr_id = "TTTC0012U" if side == "buy" else "TTTC0011U"
    headers = kis._headers(_tr_id(real_tr_id))
    if headers is None:
        return _order_failure("KIS API 키 또는 토큰을 확인하세요.")
    account_no, product_code = parts
    try:
        # Latest official samples disable hashkey; do not add that call here.
        response = requests.post(
            f"{kis.base_url()}/uapi/domestic-stock/v1/trading/order-cash",
            headers=headers,
            json={
                "CANO": account_no,
                "ACNT_PRDT_CD": product_code,
                "PDNO": symbol,
                "ORD_DVSN": "01" if order_type == "market" else "00",
                "ORD_QTY": str(qty),
                "ORD_UNPR": "0" if order_type == "market" else _price_text(price),
                "EXCG_ID_DVSN_CD": "KRX",
            },
            timeout=10,
        )
        response.raise_for_status()
        return _parse_order_response(response.json())
    except Exception:  # noqa: BLE001 - optional broker calls must stay non-fatal
        return _order_failure("KIS 주문 요청에 실패했습니다.")


def modify_cancel(
    order_no: str,
    org_no: str,
    qty: int,
    price: float | None,
    cancel: bool,
) -> dict[str, object]:
    """Modify or cancel a domestic cash order."""
    if not _order_allowed():
        return _order_failure(_REAL_ORDER_REFUSAL)
    parts = _account_parts()
    if parts is None:
        return _order_failure("KIS 계좌번호가 설정되지 않았습니다.")
    headers = kis._headers(_tr_id("TTTC0013U"))
    if headers is None:
        return _order_failure("KIS API 키 또는 토큰을 확인하세요.")
    account_no, product_code = parts
    try:
        # Latest official samples disable hashkey; do not add that call here.
        response = requests.post(
            f"{kis.base_url()}/uapi/domestic-stock/v1/trading/order-rvsecncl",
            headers=headers,
            json={
                "CANO": account_no,
                "ACNT_PRDT_CD": product_code,
                "KRX_FWDG_ORD_ORGNO": org_no,
                "ORGN_ODNO": order_no,
                "ORD_DVSN": "00",
                "RVSE_CNCL_DVSN_CD": "02" if cancel else "01",
                "ORD_QTY": str(qty),
                "ORD_UNPR": "0" if price is None else _price_text(price),
                "QTY_ALL_ORD_YN": "Y" if cancel and qty == 0 else "N",
            },
            timeout=10,
        )
        response.raise_for_status()
        return _parse_order_response(response.json())
    except Exception:  # noqa: BLE001 - optional broker calls must stay non-fatal
        return _order_failure("KIS 정정/취소 요청에 실패했습니다.")


def _parse_order_response(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        return _order_failure("KIS 주문 응답 형식이 올바르지 않습니다.")
    message_value = payload.get("msg1")
    message = message_value if isinstance(message_value, str) else "KIS 주문 응답"
    if payload.get("rt_cd") != "0":
        return _order_failure(message)
    output = payload.get("output")
    if not isinstance(output, dict):
        return _order_failure(message)
    order_no = output.get("ODNO")
    org_no = output.get("KRX_FWDG_ORD_ORGNO")
    return {
        "ok": True,
        "order_no": order_no if isinstance(order_no, str) else None,
        "org_no": org_no if isinstance(org_no, str) else None,
        "message": message,
    }


def psbl(symbol: str, price: float | None) -> dict[str, object]:
    """Fetch domestic buying power for a symbol."""
    empty: dict[str, object] = {
        "symbol": symbol,
        "orderable_cash": 0.0,
        "max_buy_qty": 0,
        "max_buy_amount": 0.0,
        "message": "",
    }
    parts = _account_parts()
    if parts is None:
        empty["message"] = "KIS 계좌번호가 설정되지 않았습니다."
        return empty
    headers = kis._headers(_tr_id("TTTC8908R"))
    if headers is None:
        empty["message"] = "KIS API 키 또는 토큰을 확인하세요."
        return empty
    account_no, product_code = parts
    try:
        response = requests.get(
            f"{kis.base_url()}/uapi/domestic-stock/v1/trading/inquire-psbl-order",
            headers=headers,
            params={
                "CANO": account_no,
                "ACNT_PRDT_CD": product_code,
                "PDNO": symbol,
                "ORD_UNPR": "0" if price is None else _price_text(price),
                "ORD_DVSN": "01",
                "CMA_EVLU_AMT_ICLD_YN": "Y",
                "OVRS_ICLD_YN": "Y",
            },
            timeout=10,
        )
        response.raise_for_status()
        data: object = response.json()
        if not isinstance(data, dict):
            empty["message"] = "KIS 매수가능금액 응답 형식이 올바르지 않습니다."
            return empty
        message_value = data.get("msg1")
        if data.get("rt_cd") != "0":
            empty["message"] = (
                message_value
                if isinstance(message_value, str)
                else "KIS 매수가능금액 조회에 실패했습니다."
            )
            return empty
        output = data.get("output")
        if not isinstance(output, dict):
            empty["message"] = "KIS 매수가능금액 응답 형식이 올바르지 않습니다."
            return empty
        return {
            "symbol": symbol,
            "orderable_cash": _number(output.get("ord_psbl_cash")),
            "max_buy_qty": _integer(
                output.get("max_buy_qty", output.get("nrcvb_buy_qty"))
            ),
            "max_buy_amount": _number(output.get("max_buy_amt")),
            "message": (
                message_value
                if isinstance(message_value, str)
                else "KIS 매수가능금액을 조회했습니다."
            ),
        }
    except Exception:  # noqa: BLE001 - optional broker calls must stay non-fatal
        empty["message"] = "KIS 매수가능금액 조회에 실패했습니다."
        return empty
