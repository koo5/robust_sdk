#!/usr/bin/env python3


import os
import sys


import defusedxml
from defusedxml.ElementTree import parse as xmlparse


fn = sys.argv[1]

h = xmlparse(fn)

for a in h.iter():
	print()
	print(a.tag)
	if a.tag == 'accountHierarchy':
		continue
	if a.tag == 'account':
		continue

	account_name = a.tag

	a.tag = 'account'
	a.set('name', account_name)

h.write(fn, encoding='utf-8', xml_declaration=True)

