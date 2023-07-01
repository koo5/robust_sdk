import click
from pymaybe import maybe, maybe_list

# https://docs.python.org/3/library/xml.etree.elementtree.html
import xml.etree.ElementTree as xmltree

import rdflib
from poetry.mixology.term import Term
from rdflib.term import Literal, BNode, Identifier
from rdflib.collection import Collection

from utils import *



class InputException(Exception):
	pass




v1 = rdflib.Namespace("'https://rdf.lodgeit.net.au/v1/")
#print(v1['request#xxxxx'])
R = 	rdflib.Namespace("'https://rdf.lodgeit.net.au/v1/request#")
E = 	rdflib.Namespace("'https://rdf.lodgeit.net.au/v1/excel#")
ER = rdflib.Namespace("'https://rdf.lodgeit.net.au/v1/excel_request#`")
BS = rdflib.Namespace("'https://rdf.lodgeit.net.au/v1/bank_statement#")
#print(R['xxxxx'])




#
g = rdflib.Graph()
#
rg = rdflib.Graph(R.request_graph)


all_request_sheets = []

def add_sheet(sheet_type: Identifier, name: str, record: Identifier):
	sheet_instance = BNode()
	rg.add(sheet_instance, E.sheet_instance_has_sheet_type, sheet_type)
	rg.add(sheet_instance, E.sheet_instance_has_sheet_name, Literal(name))
	rg.add(sheet_instance, E.sheet_instance_has_sheet_data, record)
	all_request_sheets += sheet_instance



CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option('--debug/--no-debug', default=False)
def cli(debug):
    click.echo(f"Debug mode is {'on' if debug else 'off'}")

@cli.command()
@click.argument('xml', type=click.File('r'))
def xml2rdf(xml):
	"""
	Load the legacy IC XML file and produce robust IC RDF.
	XML - path of XML file.

	"""

	#g.add((rdflib.URIRef('http://example.org/'), rdflib.RDF.type, rdflib.RDFS.Class))
	#g.add((rdflib.BNode('account'), rdflib.RDF.type, rdflib.OWL.Class))


	# finally
	# assert two facts about https://rdf.lodgeit.net.au/v1/excel_request#request in two different graphs, g and rg



	rg.add(ER.request, E.has_sheet_instances, AssertList(rg, all_request_sheets)
	g.add(ER.request, R.client_version, "3")



	x = xmltree.parse(xml).getroot()

	if not (x.tag == 'reports'):
		raise InputException('Not a valid IC XML file')
	r = x[0]
	if not (r.tag == 'balanceSheetRequest'):
		raise InputException('Not a valid IC XML file')
	for child in r:
		print(child.tag, child.attrib)



	bst= r.find('bankStatement')
	if bst is None:
		raise InputException('Not a valid IC XML file')



	for accd in bst.find("accountDetails"):
		xml_transactions = child.find('transactions')
		rdf_transactions = []
		for t in xml_transactions:

			transdesc = maybe(t.find('transdesc')).text
			transdate = t.find('transdate').text
			debit = maybe(t.find('debit')).text
			credit = maybe(t.find('credit')).text
			unit = maybe(t.find('unit')).text
			unitType = maybe(t.find('unitType')).text

			print(transdesc, transdate, debit, credit, unit, unitType)

			# add transaction to RDF graph
			tx = BNode()
			rdf_transactions += tx
			g.add(tx, R.transaction_has_description, Literal(transdesc))
			g.add(tx, R.transaction_has_date, Literal(transdate))
			g.add(tx, R.transaction_has_debit, Literal(debit))
			g.add(tx, R.transaction_has_credit, Literal(credit))
			g.add(tx, R.transaction_has_unit, Literal(unit))
			g.add(tx, R.transaction_has_unit_type, Literal(unitType))

		accountNo = child.find('accountNo').text
		accountName = child.find('accountName').text
		bankID = child.find('bankID').text
		currency = child.find('currency').text
		print(accountNo, accountName, bankID, currency)

		bs = BNode()
		g.add(bs, RDF.type, BS.bank_statement)
		g.add(bs, BS.account_currency, AssertValue(g, currency))
		g.add(bs, BS.account_name, AssertValue(g, accountName))
		g.add(bs, BS.account_number, AssertValue(g, accountNo))
		g.add(bs, BS.bank_id, AssertValue(g, bankID))
		g.add(bs, BS.items, AssertListValue(g, txs))

		sheets += add_sheet()




if __name__ == '__main__':
	cli()
