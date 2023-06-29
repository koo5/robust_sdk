import click

# https://docs.python.org/3/library/xml.etree.elementtree.html
import xml.etree.ElementTree as xmltree

import rdflib


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

	g = rdflib.Graph()
	g.add((rdflib.URIRef('http://example.org/'), rdflib.RDF.type, rdflib.OWL.Ontology))
	g.add((rdflib.BNode('account'), rdflib.RDF.type, rdflib.OWL.Class))

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
