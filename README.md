# zapret-data-generator

Генератор списков `hostlist` и `ipset` для проекта zapret на основе шаблонов и ASN-данных.

За основу взяты такие проекты как:
- [v2fly/domain-list-community](https://github.com/v2fly/domain-list-community)
- [V3nilla/IPSets-For-Bypass-in-Russia](https://github.com/V3nilla/IPSets-For-Bypass-in-Russia)

## 📌 Возможности

- Генерация `hostlist` и `ipset` из шаблонов
- Поддержка `include`-структуры
- Фильтрация по атрибутам (`@cn`, `@!ads` и т.д.)
- Автоматическая загрузка IP-префиксов по ASN (через RIPE API)
- Агрегация и оптимизация IP-сетей
- Поддержка IPv4 и IPv6

---

## ⚠️ Ограничения
- regexp шаблоны не возможны в zapret

---

## 🚀 Использование

``` bash
python main.py
```

### Что делает `main.py`

1.  Генерирует `hostlist`
2.  Загружает ASN IP-сети
3.  Генерирует `ipset`

---

## ⭐ Статискика проекта

[![Star History
Chart](https://api.star-history.com/svg?repos=fluffydaddy/zapret-data-generator&type=Date)](https://star-history.com/#fluffydaddy/zapret-data-generator&Date)
