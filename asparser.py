#!/usr/bin/env python3
import argparse
import requests
import ipaddress
import time
import re
import os
from dataclasses import dataclass, field
from typing import List, Optional, Union

@dataclass
class ASNRecord:
    value: str                     # основной ASN
    company: Optional[str] = None  # название компании
    country: Optional[str] = None  # код страны
    registry: str = "RIPE"         # регистратор
    website: str = None            # вебсайт
    type_: Optional[Union[str, list]] = None  # тип/категории, например "hosting", "cdn", "inactive"

    @classmethod
    def normalize(cls, data: Union[str, dict, "ASNRecord"]):
        """Превращает строку, словарь или ASNRecord в ASNRecord"""
        if isinstance(data, cls):
            return data
        if isinstance(data, str):
            return cls(value=data)
        if isinstance(data, dict):
            type_field = data.get("type")
            registry_field = data.get("registry")
            website_field = data.get("website")
            # приводим строку к списку, если нужно
            if isinstance(type_field, str):
                type_field = [t.strip() for t in type_field.split("|") if t.strip()]
            return cls(
                value=data["value"],
                company=data.get("company"),
                country=data.get("country"),
                registry=registry_field.lower(),
                website=website_field,
                type_=type_field,
            )
        raise TypeError(f"ASNRecord must be str, dict or ASNRecord, got {type(data)}")

    def is_active(self) -> bool:
        """Возвращает True, если ASN не имеет 'inactive' в type_"""
        if self.type_ is None:
            return True
        if isinstance(self.type_, str):
            return self.type_.lower() != "inactive"
        if isinstance(self.type_, list):
            return "inactive" not in [t.lower() for t in self.type_]
        return True

@dataclass
class ASN:
    name: str
    asn: Union[str, dict, ASNRecord, List[Union[str, dict, ASNRecord]]]
    output: str
    enabled: bool = True
    category: Optional[Union[str, List[str]]] = None

    def __post_init__(self):
        # 1) Нормализуем ASN в список объектов ASNRecord
        if isinstance(self.asn, (str, dict, ASNRecord)):
            self.asn = [ASNRecord.normalize(self.asn)]
        elif isinstance(self.asn, list):
            self.asn = [ASNRecord.normalize(a) for a in self.asn]
        else:
            raise TypeError(f"asn must be str, dict, ASNRecord or list, got {type(self.asn)}")

        # 2) Фильтруем inactive по type_
        self.asn = [a for a in self.asn if a.is_active()]

        # 3) Нормализуем категории
        if isinstance(self.category, str):
            self.category = [c.strip() for c in self.category.split("|") if c.strip()]
        elif self.category is not None and not isinstance(self.category, list):
            raise TypeError(f"category must be str or list of str, got {type(self.category)}")

def detect_format_from_file(path: str) -> str:
    """Определяет формат конфигурации по расширению файла"""
    ext_map = {
        ".json": "json",
        ".jsonc": "json5",
        ".json5": "json5",
        ".yaml": "yaml",
        ".yml": "yaml",
    }
    ext = os.path.splitext(path)[1].lower()
    fmt = ext_map.get(ext)
    if fmt is None:
        raise ValueError(f"Cannot determine config format from extension '{ext}'")
    return fmt

def get_loader(fmt: str):
    loaders = {
        "json": lambda path: __import__("json").load(open(path, "r", encoding="utf-8")),
        "json5": lambda path: __import__("json5").load(open(path, "r", encoding="utf-8")),
        "yaml": lambda path: __import__("yaml").safe_load(open(path, "r", encoding="utf-8")),
    }
    loader = loaders.get(fmt)
    if loader is None:
        raise ValueError(f"No loader available for format {fmt}")
    return loader

def load_config(path: str, format: str = "json5") -> List[ASN]:
    loader = get_loader(format)
    raw = loader(path)

    if not isinstance(raw, list):
        raise ValueError("Top-level structure must be a list of objects")

    return [ASN(**item) for item in raw]

def load_config_auto(path: str) -> List[ASN]:
    return load_config(path, detect_format_from_file(path))

def run():
    API_URL = "https://stat.ripe.net/data/announced-prefixes/data.json"
    API_DELAY = 1.0

    parser = argparse.ArgumentParser(
        description="ASN Parser"
    )
    parser.add_argument(
        "-f",
        "--input",
        help="Входной файл asn_list.json[c]",
        default="asn_list.jsonc"
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Выходной файл шаблон"
    )
    # Added before original filename. e.g. ipset-
    parser.add_argument(
        "-p",
        "--prefix",
        help="Префикс имен файлов добавляемые к каждому выходному файлу",
        default=""
    )
    # Added after original filename. e.g. .txt
    parser.add_argument(
        "-s",
        "--suffix",
        help="Суффикс имен файлов добавляемые к каждому выходному файлу",
        default=""
    )
    parser.add_argument(
        "-d",
        "--destination",
        help="Путь до папки выходных файлов",
        default="data/ipset"
    )
    parser.add_argument(
        "-t",
        "--timeout",
        help="Таймаут для API",
        type=int,
        default=15
    )
    args = parser.parse_args()

    ASN_LIST = load_config_auto(args.input)
    TIMEOUT = args.timeout
    DESTINATION = args.destination
    FILE_PREFIX = args.prefix
    FILE_SUFFIX = args.suffix

    IPSET_ALL_TEMPLATE_FILE = None

    if args.output:
        IPSET_ALL_TEMPLATE_FILE = open(args.output, "w", encoding="utf-8")

    for service in ASN_LIST:
        if not service.enabled:
            continue
        if IPSET_ALL_TEMPLATE_FILE:
            IPSET_ALL_TEMPLATE_FILE.write(f"include:{service.output}\n")
            continue
        v4_all = set()
        v6_all = set()

        print(f"[+] Обработка {service.name} ({[a.value for a in service.asn]}) ...", flush=True)

        for asn_record in service.asn:
            asn_value = asn_record.value
            try:
                r = requests.get(
                    API_URL,
                    params={"resource": asn_value, "min_peers_seeing": 1},
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

                print(f"    - {asn_value}: {count} префиксов добавлено")
            except Exception as e:
                print(f"    Ошибка при получении {asn_value}: {e}")
            time.sleep(API_DELAY)

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

    if IPSET_ALL_TEMPLATE_FILE:
        IPSET_ALL_TEMPLATE_FILE.close()

    print("\nГотово!")

if __name__ == "__main__":
    run()
