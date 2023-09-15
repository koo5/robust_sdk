from loguru import logger
import rdflib
from rdflib.term import Literal, BNode, Identifier, URIRef
from rdflib.collection import Collection
from robust_sdk.prefixes import *
import click



logger.debug("That's it, beautiful and simple logging!")



@click.command()
@click.argument('templates_fn', type=click.File('r'))
@click.argument('fn1', type=click.File('r'))
@click.argument('fn2', type=click.File('r'))
def compare_sheetsets(templates_fn, fn1, fn2):
	
	logger.debug(f"load {templates_fn}")
	t=rdflib.ConjunctiveGraph()
	t.parse(templates_fn, format='trig')
	
	logger.debug(f"load {fn1}")
	f1=rdflib.ConjunctiveGraph()
	f1.parse(fn1, format='trig')
	
	#logger.debug(f"load {fn2}")
	#f2=rdflib.ConjunctiveGraph()
	#f2.parse(fn2, format='trig')

	request_uri = 'https://rdf.lodgeit.net.au/v1/excel_request#request'
	request = URIRef(request_uri)
	sheet_instances = URIRef('https://rdf.lodgeit.net.au/v1/excel#has_sheet_instances')

	#print(list(f1.triples((None, None, None))))

	for x in Collection(f1, one(f1.objects(request, sheet_instances))):
		data = one(f1.objects(x, E.sheet_instance_has_sheet_data))
		name = one(f1.objects(x, E.sheet_instance_has_sheet_name))
		type = one(f1.objects(x, E.sheet_instance_has_sheet_type))
		template = one(f1.objects(data, E.template))
		print(f"sheet: {name} ({type}) ({template}):")
		walk_record(t, f1, template, data)

def walk_record(templates, f1, template, data):
	if template == 
	print(f"record with template: {template}")
	cardinality = one(templates.objects(template, E.cardinality))
	if cardinality == E.multi:
		items = list(Collection(f1, one(f1.objects(data, RDF.value))))
		print(f"is multi with items {items}")
		for idx,x in enumerate(items):
			print(f"item {idx}:")
			walk_item(templates, f1, template, x)
	else:
		print("single")
		walk_item(templates, f1, template, data)
		
def walk_item(templates, f1, template, data):
	fields = Collection(templates, one(templates.objects(template, E.fields)))
	for field in fields:
		field_property = one(templates.objects(field, E.property))
		field_type = list(templates.objects(field, E.type))
		if len(field_type) != 1:
			field_type = one(templates.objects(field, E.template))
		field_values = list(f1.objects(data, field_property))
		print(f"field: {field_property} ({field_type}) {field_values}")
		if len(field_values) == 1:
			field_value = field_values[0]
			walk_record(templates, f1, field_type, field_value)
		elif len(field_values) == 0:
			print("no value")
		else:
			raise ValueError(f"expected one or zero values, got {len(field_values)}")


def one(generator):
	l = list(generator)
	if len(l) != 1:
		raise ValueError(f"expected one element, got {len(l)}")
	return l[0]

if __name__ == '__main__':
	compare_sheetsets()

