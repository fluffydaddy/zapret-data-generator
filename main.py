#!/usr/bin/env python3
import sys
import generator
import asparser

def run_generator(args):
    sys.argv = ["generator.py"] + args
    generator.main()

def main():
    # 1. hostlist
    run_generator(["hostlist", "list-general.template", "list-general.txt"])

    # 2. ASN parser
    asparser.main()

    # 3. ipset
    run_generator(["ipset", "ipset-all.template", "ipset-all.txt"])

if __name__ == "__main__":
    main()