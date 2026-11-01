"""Read official Cloud Billing Catalog SKUs with ADC; never guess SKU mappings."""
from __future__ import annotations

import argparse
from pathlib import Path

from google.cloud import billing_v1
from google.protobuf.json_format import MessageToDict

from benchmark.io import utcnow, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-services", action="store_true")
    parser.add_argument("--service-id", help="Numeric service ID obtained with --list-services")
    parser.add_argument("--region", default="asia-southeast1")
    parser.add_argument("--output", type=Path, default=Path("results/billing_catalog.json"))
    args = parser.parse_args()
    client = billing_v1.CloudCatalogClient()
    if args.list_services:
        for service in client.list_services():
            print(service.name, service.display_name)
        return
    if not args.service_id or not all(ch.isalnum() or ch == "-" for ch in args.service_id):
        parser.error("Cần --service-id hợp lệ hoặc --list-services")
    name = "services/" + args.service_id
    records = []
    for sku in client.list_skus(request={"parent": name, "currency_code": "USD"}):
        if args.region in sku.service_regions or "global" in sku.service_regions:
            records.append(MessageToDict(sku._pb, preserving_proto_field_name=True))
    write_json(args.output, {"retrieved_at": utcnow(), "region": args.region, "currency": "USD", "source": "https://cloud.google.com/billing/docs/reference/rest/v1/services.skus/list", "service": name, "skus": records, "note": "Raw tiered rates and effective_time preserved. Review usage_unit/conversion_factor/tiers/geo_taxonomy before mapping to pricing_catalog.yaml; this script does not overwrite prices."})
    print(args.output, len(records))


if __name__ == "__main__":
    main()
