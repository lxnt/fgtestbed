#!/usr/bin/python3.2

import yaml, sys, pprint

pprint.pprint(list(yaml.safe_load_all(open(sys.argv[1], 'r'))))

