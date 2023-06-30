import click

# https://docs.python.org/3/library/xml.etree.elementtree.html
import xml.etree.ElementTree as xmltree

import rdflib
from poetry.mixology.term import Term
from rdflib.term import Literal, BNode, Identifier
from rdflib.collection import Collection




def AssertList(g, seq: List[Node]):
	c = Collection(g, None, seq)
	return c.uri


class InputException(Exception):
	pass


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



	v1 = rdflib.Namespace("'https://rdf.lodgeit.net.au/v1/")
	#print(v1['request#xxxxx'])
	R = rdflib.Namespace("'https://rdf.lodgeit.net.au/v1/request#")
	E = rdflib.Namespace("'https://rdf.lodgeit.net.au/v1/excel#")
	ER = rdflib.Namespace("'https://rdf.lodgeit.net.au/v1/excel_request#")
	#print(R['xxxxx'])


	#
	g = rdflib.Graph()
	#
	rg = rdflib.Graph(R.request_graph)




	# finally
	# assert two facts about https://rdf.lodgeit.net.au/v1/excel_request#request in two different graphs





	def add_sheet(Identifier sheet_type, str name, Identifier record):
		sheet_instance = BNode()
			rg.add(sheet_instance, E.sheet_instance_has_sheet_type, sheet_type)
			rg.add(sheet_instance, E.sheet_instance_has_sheet_name, Literal(name))
			rg.add(sheet_instance, E.sheet_instance_has_sheet_data, record)
			all_request_sheets.Add(sheet_instance);





	all_request_sheets = [
		add_sheet(

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
	for child in bst:
		print(child.tag, child.attrib)
		if child.tag == 'accountDetails':

			accountNo = child.find('accountNo').text
			accountName = child.find('accountName').text
			bankID = child.find('bankID').text
			currency = child.find('currency').text
			print(accountNo, accountName, bankID, currency)
			transactions = child.find('transactions')
			for t in transactions:

				transdesc = t.find('transdesc')
				if transdesc is not None:
					transdesc = transdesc.text
				transdate = t.find('transdate').text
				debit = t.find('debit')
				if debit is not None:
					debit = debit.text
				credit = t.find('credit')
				if credit is not None:
					credit = credit.text
				unit = t.find('unit')
				if unit is not None:
					unit = unit.text
				unitType = t.find('unitType')
				if unitType is not None:
					unitType = unitType.text

				print(transdesc, transdate, debit, credit, unit, unitType)





if __name__ == '__main__':
	cli()
