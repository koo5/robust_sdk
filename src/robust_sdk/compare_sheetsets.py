from loguru import logger
import rdflib
from rdflib.term import Literal, BNode, Identifier, URIRef
from .prefixes import *
import click



logger.debug("That's it, beautiful and simple logging!")



@click.command()
@click.argument('templates', type=click.File('r'))
@click.argument('fn1', type=click.File('r'))
@click.argument('fn2', type=click.File('r'))
def compare_sheetsets(templates, fn1, fn2):
	logger.debug(f"load {templates}")
	t=rdflib.Graph().parse(templates, format='trig')
	logger.debug(f"load {fn1}")
	f1=rdflib.Graph().parse(fn1, format='trig')
	logger.debug(f"load {fn2}")
	f2=rdflib.Graph().parse(fn2, format='trig')

	request_uri = 'https://rdf.lodgeit.net.au/v1/excel_request#request'
	request = URIRef(request_uri)
	sheet_instances = URIRef('https://rdf.lodgeit.net.au/v1/excel#has_sheet_instances')

	print(list(f1.objects(request, sheet_instances)))



if __name__ == '__main__':
	cli()

