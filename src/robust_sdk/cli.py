import click
from pymaybe import maybe

# https://docs.python.org/3/library/xml.etree.elementtree.html
import xml.etree.ElementTree as xmltree

import rdflib
from poetry.mixology.term import Term
from rdflib.term import Literal, BNode, Identifier
from rdflib.collection import Collection

from datetime import datetime

from utils import *



class InputException(Exception):
	pass




V1 = rdflib.Namespace("'https://rdf.lodgeit.net.au/v1/")
R = 	rdflib.Namespace("'https://rdf.lodgeit.net.au/v1/request#")
E = 	rdflib.Namespace("'https://rdf.lodgeit.net.au/v1/excel#")
ER = rdflib.Namespace("'https://rdf.lodgeit.net.au/v1/excel_request#")
BS = rdflib.Namespace("'https://rdf.lodgeit.net.au/v1/bank_statement#")
IC = rdflib.Namespace("'https://rdf.lodgeit.net.au/v1/calcs/ic#")
IC_UI = rdflib.Namespace("'https://rdf.lodgeit.net.au/v1/calcs/ic/ui#")




#
g = rdflib.Graph()
#
rg = rdflib.Graph(identifier = R.request_graph)


all_request_sheets = []

def add_sheet(sheet_type: Identifier, name: str, record: Identifier):
	sheet_instance = BNode()#'sheet_instance')
	rg.add((sheet_instance, E.sheet_instance_has_sheet_type, sheet_type))
	rg.add((sheet_instance, E.sheet_instance_has_sheet_name, Literal(name)))
	rg.add((sheet_instance, E.sheet_instance_has_sheet_data, record))
	all_request_sheets.append(sheet_instance)

def date_literal(date_str: str):
	return Literal(datetime.strptime(date_str, '%y-%m-%d')



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



	x = xmltree.parse(xml).getroot()

	if not (x.tag == 'reports'):
		raise InputException('Not a valid IC XML file')
	r = x[0]
	if not (r.tag == 'balanceSheetRequest'):
		raise InputException('Not a valid IC XML file')
	#for child in r:
	#	print(child.tag, child.attrib)
	AssertValue(date_literal(r.find('startDate').text))
	AssertValue(date_literal(r.find('endDate').text))


	report_details = BNode()#'bank_statement')
	g.add((report_details, RDF.type, BS.report_details))

	g.add((report_details, IC.cost_or_market,			 AssertValue(g, IC.cost)))
	g.add((report_details, IC.currency,					 AssertLiteralValue(g, r.find('reportCurrency').text)))
	g.add((report_details, IC['from'],					 AssertValue(g, date_literal(r.find('startDate').text))))
	g.add((report_details, IC['to'],						 AssertValue(g, date_literal(r.find('endDate').text))))
	g.add((report_details, IC.pricing_method,			 AssertValue(g, IC.lifo)))

	taxonomy1 = BNode(); g.add((taxonomy1, V1['account_taxonomies#url'],  V1['account_taxonomies#base']))
	taxonomy2 = BNode(); g.add((taxonomy2, V1['account_taxonomies#url'],  V1['account_taxonomies#investments']))
	#taxonomy3 = BNode(); g.add((taxonomy3, V1['account_taxonomies#url'],  V1['account_taxonomies#livestock']))
	account_taxonomies = [
		AssertValue(g, taxonomy1),
		AssertValue(g, taxonomy2),
		#AssertValue(g, taxonomy3)
	]
	g.add((report_details, IC_UI.account_taxonomies,		 AssertListValue(g, account_taxonomies)))
	add_sheet(IC_UI.report_details_sheet, 'report_details', report_details)





	defaultCurrency = r.find('defaultCurrency').text


	bst= r.find('bankStatement')
	if bst is None:
		raise InputException('Not a valid IC XML file')



	for accd in bst.findall("accountDetails"):
		xml_transactions = accd.find('transactions')
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
			tx = BNode()#'tx')
			rdf_transactions.append(tx)
			g.add((tx, R.transaction_has_description, Literal(transdesc)))
			g.add((tx, R.transaction_has_date, Literal(transdate)))
			g.add((tx, R.transaction_has_debit, Literal(debit)))
			g.add((tx, R.transaction_has_credit, Literal(credit)))
			g.add((tx, R.transaction_has_unit, Literal(unit)))
			g.add((tx, R.transaction_has_unit_type, Literal(unitType)))

		fff =child.find('accountNo')
		accountNo = accd.find('accountNo').text
		accountName = accd.find('accountName').text
		bankID = accd.find('bankID').text
		currency = accd.find('currency').text
		print(accountNo, accountName, bankID, currency)

		bs = BNode()#'bank_statement')
		g.add((bs, RDF.type, BS.bank_statement))
		g.add((bs, BS.account_currency, AssertLiteralValue(g, currency)))
		g.add((bs, BS.account_name, AssertLiteralValue(g, accountName)))
		g.add((bs, BS.account_number, AssertLiteralValue(g, accountNo)))
		g.add((bs, BS.bank_id, AssertLiteralValue(g, bankID)))
		g.add((bs, BS.items, AssertListValue(g, rdf_transactions)))

		add_sheet(IC_UI.bank_statement_sheet, accountName, bs)


	# finally, assert two facts about https://rdf.lodgeit.net.au/v1/excel_request#request in two different graphs, g and rg
	rg.add((ER.request, E.has_sheet_instances, AssertList(rg, all_request_sheets)))
	g.add((ER.request, R.client_version, Literal("3")))

	# i think this is guaranteed not to produce collisions of bnodes names, since all bnodes are generated by calling BNode(), which uses uuid4()
	result_graph = g + rg
	result_graph.serialize('result.trig', format='trig')


	print()
	print('vvvv')
	print(result_graph.serialize(format='turtle'))
	print('^^^^')
	print()


if __name__ == '__main__':
	cli()



#g.add((rdflib.URIRef('http://example.org/'), rdflib.RDF.type, rdflib.RDFS.Class))


