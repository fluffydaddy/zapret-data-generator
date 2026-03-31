@echo off

python generator.py hostlist list-general.template list-general.txt

python asparser.py
python generator.py ipset ipset-all.template ipset-all.txt