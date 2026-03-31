#!/usr/bin/env python3
import requests
import ipaddress
import time
import json
import re
from dataclasses import dataclass

@dataclass
class ASN:
    name: str       # hetzner
    asn: list  # ["AS24940", "AS213230"]
    output: str     # filename
    enabled: bool   # include ASN list this boolean flag true/false, default: true

def load_jsonc(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # delete // comments
    content = re.sub(r"//.*", "", content)

    # delete /* */ comments
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)

    return json.loads(content)

def load_asn_list(path):
    raw = load_jsonc(path)
    result = []

    for i, item in enumerate(raw):
        if not all(k in item for k in ("name", "asn", "output")):
            raise ValueError(f"Ошибка в записи #{i}: {item}")

        result.append(
            ASN(
                name=item.get("name"),
                asn=item.get("asn"),
                output=item.get("output"),
                enabled=item.get("enabled", True)
            )
        )

    return result

ASN_LIST = load_asn_list("asn_list.jsonc")

API_URL = "https://stat.ripe.net/data/announced-prefixes/data.json"
TIMEOUT = 15  # секунд

DESTINATION = "data/ipset"

# Added before original filename. e.g. ipset-
FILE_PREFIX = ""

# Added after original filename. e.g. .txt
FILE_SUFFIX = ""

for service in ASN_LIST:
    if not service.enabled:
        continue
    
    v4_all = set()
    v6_all = set()

    print(f"[+] Обработка {service.name} ({service.asn}) ...", flush=True)

    for asn in service.asn:
        try:
            r = requests.get(
                API_URL,
                params={"resource": asn, "min_peers_seeing": 1},
                timeout=TIMEOUT
            )
            r.raise_for_status()
            data = r.json().get("data", {}).get("prefixes", [])
            count = 0

            for p in data:
                prefix = p.get("prefix")
                if not prefix:
                    continue
                try:
                    net = ipaddress.ip_network(prefix, strict=False)
                    if net.prefixlen == 0:
                        continue
                    if not net.is_global:
                        continue
                    if net.version == 4:
                        v4_all.add(net)
                    else:
                        v6_all.add(net)
                    count += 1
                except Exception:
                    continue

            print(f"    {asn}: {count} префиксов добавлено")
        except Exception as e:
            print(f"    Ошибка при получении {asn}: {e}")

        time.sleep(1.0)  # чтобы не бомбить API

    v4_agg = list(ipaddress.collapse_addresses(
        sorted(v4_all, key=lambda n: (int(n.network_address), n.prefixlen))
    ))
    v6_agg = list(ipaddress.collapse_addresses(
        sorted(v6_all, key=lambda n: (int(n.network_address), n.prefixlen))
    ))

    def sort_key(n):
        return (n.version, int(n.network_address), n.prefixlen)

    v4_sorted = sorted(v4_agg, key=sort_key)
    v6_sorted = sorted(v6_agg, key=sort_key)

    output = f"{DESTINATION}/{FILE_PREFIX}{service.output}{FILE_SUFFIX}"

    with open(output, "w", encoding="utf-8") as f:
        for net in v4_sorted:
            f.write(str(net) + "\n")
        for net in v6_sorted:
            f.write(str(net) + "\n")

    print(f"Сохранено в {output}")
    print(f"IPv4: {len(v4_sorted)} | IPv6: {len(v6_sorted)} | Всего: {len(v4_sorted)+len(v6_sorted)}")

print("\nГотово!")
