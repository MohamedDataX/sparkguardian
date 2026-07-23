"""Cloud instance pricing — live lookups with a transparent fallback.

The estimator needs a real hourly price for the cluster's instance type. This
module fetches it from the cloud provider when possible and, crucially, NEVER
crashes the CLI: any missing dependency, missing credential, network error or
timeout silently falls back to a built-in on-demand price table.

Providers:
  - AWS      : boto3 ``pricing`` client (us-east-1). Optional dependency.
  - Azure    : public retail-prices REST API (no auth). Needs ``requests``/httpx.
  - GCP      : no clean unauthenticated catalog API → always uses the table.
  - Databricks: priced as its underlying VM here; the DBU surcharge is added by
    the estimator, not by this module.

All lookups are memoised with ``functools.lru_cache`` so a run hits the network
at most once per (cloud, instance_type).
"""
from __future__ import annotations

import logging
from functools import lru_cache

log = logging.getLogger(__name__)

# Default on-demand USD/hour, Linux, us-east-1, shared tenancy (2025 list prices).
# Used whenever a live lookup is unavailable — which is the common case offline.
_DEFAULT_HOURLY_USD: dict[str, float] = {
    # Graviton (m6g) — the estimator's reference family
    "m6g.large": 0.077,
    "m6g.xlarge": 0.154,
    "m6g.2xlarge": 0.308,
    "m6g.4xlarge": 0.616,
    # General purpose x86
    "m5.xlarge": 0.192,
    "m5.2xlarge": 0.384,
    "m6i.xlarge": 0.192,
    "m6i.2xlarge": 0.384,
    # Compute optimised
    "c6g.xlarge": 0.136,
    "c5.xlarge": 0.170,
    # Memory optimised
    "r6g.xlarge": 0.2016,
    "r5.xlarge": 0.252,
    # Storage optimised
    "i3.xlarge": 0.312,
}

# Last-resort price when the instance type is unknown everywhere: assume a
# 4-vCPU node at the m6g per-vCPU rate. Keeps estimates finite, never zero.
_FALLBACK_HOURLY_USD = 0.154

# Relative on-demand level of the same class across providers, applied only to
# the fallback table (a live API already returns the provider's real price).
_PROVIDER_FACTOR: dict[str, float] = {
    "aws": 1.0,
    "aws_emr": 1.0,
    "databricks": 1.0,   # VM part only; DBU added by the estimator
    "gcp": 0.94,
    "gcp_dataproc": 0.94,
    "azure": 1.05,
    "azure_synapse": 1.05,
}

# Default Databricks DBU price, USD per DBU-hour.
# $0.15 = Jobs Compute, Premium tier on AWS (the tier for scheduled ETL, which
# is what SparkGuardian analyses). Verified 2025-2026; the old $0.40 figure was
# All-Purpose Standard, and the Standard tier was retired on AWS in Oct 2025.
# Assumes ~1 DBU per node-hour for a reference xlarge node.
DEFAULT_DBU_PRICE = 0.15

_NETWORK_TIMEOUT = 5.0


def _normalise(cloud: str) -> str:
    """Collapse the workload's cloud id to a bare provider name."""
    c = cloud.lower()
    if c.startswith("aws") or c == "databricks":
        return "databricks" if c == "databricks" else "aws"
    if c.startswith("gcp"):
        return "gcp"
    if c.startswith("azure"):
        return "azure"
    return c


def _table_price(cloud: str, instance_type: str) -> float:
    base = _DEFAULT_HOURLY_USD.get(instance_type, _FALLBACK_HOURLY_USD)
    factor = _PROVIDER_FACTOR.get(cloud.lower(), 1.0)
    return round(base * factor, 4)


def _aws_live_price(instance_type: str) -> float | None:
    """Query the AWS Price List API. Returns None on any problem."""
    try:
        import json

        import boto3  # optional
    except ImportError:
        return None
    try:
        client = boto3.client("pricing", region_name="us-east-1")
        resp = client.get_products(
            ServiceCode="AmazonEC2",
            Filters=[
                {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type},
                {"Type": "TERM_MATCH", "Field": "location", "Value": "US East (N. Virginia)"},
                {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
                {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
                {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
                {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"},
            ],
            MaxResults=1,
        )
        for item in resp.get("PriceList", []):
            product = json.loads(item)
            terms = product["terms"]["OnDemand"]
            for term in terms.values():
                for dim in term["priceDimensions"].values():
                    price = float(dim["pricePerUnit"]["USD"])
                    if price > 0:
                        return price
    except Exception as exc:  # noqa: BLE001 - never let pricing break the CLI
        log.debug("AWS pricing lookup failed: %s", exc)
    return None


def _azure_live_price(instance_type: str) -> float | None:
    """Query Azure's public retail-prices API. Returns None on any problem."""
    try:
        import httpx  # already a project dependency
    except ImportError:
        try:
            import requests as httpx  # type: ignore[no-redef]
        except ImportError:
            return None
    url = "https://prices.azure.com/api/retail/prices"
    flt = (
        "serviceName eq 'Virtual Machines' "
        "and armRegionName eq 'westeurope' "
        f"and skuName eq '{instance_type}'"
    )
    try:
        resp = httpx.get(url, params={"$filter": flt}, timeout=_NETWORK_TIMEOUT)
        items = resp.json().get("Items", [])
        for item in items:
            # Skip spot/low-priority SKUs — we want the on-demand rate.
            name = (item.get("skuName", "") + item.get("meterName", "")).lower()
            if "spot" in name or "low priority" in name:
                continue
            price = float(item.get("retailPrice", 0) or 0)
            if price > 0:
                return price
    except Exception as exc:  # noqa: BLE001
        log.debug("Azure pricing lookup failed: %s", exc)
    return None


class CloudPricingFetcher:
    """Resolves an instance's hourly price, live when possible, table otherwise."""

    @staticmethod
    @lru_cache(maxsize=128)
    def get_instance_price(cloud: str, instance_type: str) -> float:
        """Hourly on-demand USD for ``instance_type`` on ``cloud``.

        Always returns a positive float. Tries the provider's API first, then
        the built-in table. Memoised per argument pair.
        """
        provider = _normalise(cloud)
        live: float | None = None
        if provider in ("aws", "databricks"):
            live = _aws_live_price(instance_type)
        elif provider == "azure":
            live = _azure_live_price(instance_type)
        # GCP and every failed lookup land on the table.

        if live is not None and live > 0:
            log.debug("live price %s/%s = $%.4f/h", cloud, instance_type, live)
            return round(live, 4)

        price = _table_price(cloud, instance_type)
        log.debug("table price %s/%s = $%.4f/h", cloud, instance_type, price)
        return price

    @staticmethod
    def dbu_price() -> float:
        """Databricks DBU price (USD/DBU-hour)."""
        return DEFAULT_DBU_PRICE
