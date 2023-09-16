from loguru import logger
import rdflib
from rdflib.term import Literal, BNode, Identifier, URIRef
from rdflib.collection import Collection
from robust_sdk.prefixes import *
import click

logger.debug("That's it, beautiful and simple logging!")

warnings = []

def warn(msg):
	logger.warning(msg)
	warnings.append(msg)


@click.command()
@click.argument('templates_fn', type=click.File('r'))
@click.argument('fn1', type=click.File('r'))
@click.argument('fn2', type=click.File('r'))
def compare_sheetsets(templates_fn, fn1, fn2):
	logger.debug(f"load {templates_fn}")
	t = rdflib.ConjunctiveGraph()
	t.parse(templates_fn, format='trig')

	logger.debug(f"load {fn1}")
	f1 = rdflib.ConjunctiveGraph()
	f1.parse(fn1, format='trig')

	logger.debug(f"load {fn2}")
	f2 = rdflib.ConjunctiveGraph()
	f2.parse(fn2, format='trig')

	# print(list(f1.triples((None, None, None))))

	for templatedef in [t, f1, f2]:
		m = f"using templatedef: {templatedef.identifier}"
		logger.info(m)
		if len(warnings) > 0:
			logger.warning(m)

		walk_sheetset(templatedef, f1, f2)

	if len(warnings) > 0:
		logger.warning(f"warnings:")
		for w in warnings:
			logger.warning(w)


def walk_sheetset(t, f1, f2):
	request_uri = 'https://rdf.lodgeit.net.au/v1/excel_request#request'
	request = URIRef(request_uri)
	sheet_instances = URIRef('https://rdf.lodgeit.net.au/v1/excel#has_sheet_instances')

	f1_sheets = Collection(f1, one(f1.objects(request, sheet_instances)))
	f2_sheets = Collection(f2, one(f2.objects(request, sheet_instances)))
	if len(f1_sheets) != len(f2_sheets):
		warn(f"unequal number of sheets: {len(f1_sheets)} vs {len(f2_sheets)}")

	for idx,x in enumerate(f1_sheets):
		if len(f2_sheets) <= idx:
			warn(f"sheetset item {idx} is missing from f2")
			return
		y = f2_sheets[idx]

		f1_data = one(f1.objects(x, E.sheet_instance_has_sheet_data))
		f1_name = one(f1.objects(x, E.sheet_instance_has_sheet_name))
		f1_type = one(f1.objects(x, E.sheet_instance_has_sheet_type))
		f2_data = one(f2.objects(y, E.sheet_instance_has_sheet_data))
		f2_name = one(f2.objects(y, E.sheet_instance_has_sheet_name))
		f2_type = one(f2.objects(y, E.sheet_instance_has_sheet_type))
		
		if f1_name != f2_name:
			warn(f"sheetset item {idx} has different names: {f1_name} vs {f2_name}")
		if f1_type != f2_type:
			warn(f"sheetset item {idx} has different types: {f1_type} vs {f2_type}")

		f1_template = one(f1.objects(f1_data, E.template))
		f2_template = one(f2.objects(f2_data, E.template))
		if f1_template != f2_template:
			warn(f"sheetset {idx} root item has different templates: {f1_template} vs {f2_template}")

		print(f"sheet: {f1_name} ({f1_type}) ({f1_template}):")
		walk_record(t, f1, f2, f1_template, f1_data, f2_data)

def check_record_template(template, data, f):
	t = one(f.objects(data, E.template))
	if template != t:
		warn(f"record has different template than declared in parent structure: {template} vs {one(f.objects(data, E.template))}")

def read_unknown_field_decls(f, record):
	l = list(f.objects(record, E.has_unknown_fields))
	if len(l) == 0:
		return []
	elif len(l) == 1:
		for uri in list(Collection(f, l[0])):
			yield uri, one(f.objects(uri, E.has_header_cell_value))

	else:
		raise ValueError(f"expected one or zero unknown field declarations, got {len(l)}")

def check_unknown_field_decls(f1_unknown_field_decls, f2_unknown_field_decls):
	# they technically don't have to have equal names, but they will
	if len(f1_unknown_field_decls) != len(f2_unknown_field_decls):
		warn(f"unequal number of unknown fields: {len(f1_unknown_field_decls)} vs {len(f2_unknown_field_decls)}")
	
	for idx, d in enumerate(f1_unknown_field_decls):
		if len(f2_unknown_field_decls) <= idx:
			warn(f"unknown field {idx} is missing from f2")
			return
		if d != f2_unknown_field_decls[idx]:
			warn(f"unknown field {idx} differs: {d} vs {f2_unknown_field_decls[idx]}")


def walk_record(templates, f1, f2, template, f1_data, f2_data):
	print(f"record with template: {template}")
	check_record_template(template, f1_data, f1)
	check_record_template(template, f2_data, f2)
	f1_unknown_field_decls = list(read_unknown_field_decls(f1, f1_data))
	f2_unknown_field_decls = list(read_unknown_field_decls(f2, f2_data))
	check_unknown_field_decls(f1_unknown_field_decls, f2_unknown_field_decls)	

	cardinality = one(templates.objects(template, E.cardinality))
	if cardinality == E.multi:
		items1 = list(Collection(f1, one(f1.objects(f1_data, RDF.value))))
		items2 = list(Collection(f2, one(f2.objects(f2_data, RDF.value))))
		if len(items1) != len(items2):
			warn(f"unequal number of items: {len(items1)} vs {len(items2)}")
		print(f"is multi with items(rows) {items1}")
		for idx, x in enumerate(items1):
			if len(items2) <= idx:
				warn(f"item {idx} is missing from f2")
				return
			print(f"fields of item {idx}:")
			y = items2[idx]
			walk_fields(templates, f1, f2, template, x, y, f1_unknown_field_decls, f2_unknown_field_decls)
	else:
		print("single")
		walk_fields(templates, f1, f2, template, f1_data, f2_data, f1_unknown_field_decls, f2_unknown_field_decls)


def walk_fields(templates, f1, f2, template, f1_data, f2_data, f1_unknown_field_decls, f2_unknown_field_decls):
	fields = Collection(templates, one(templates.objects(template, E.fields)))

	for idx, (f1_uf_prop,f1_uf_title) in enumerate(f1_unknown_field_decls):
		print(f"field: {f1_uf_prop}")
		f2_uf_prop = f2_unknown_field_decls[idx][0]
		visit_field(templates, f1, f2, template, f1_data, f2_data, None, 'stringgg', f1_uf_prop, f2_uf_prop)

	for field in fields:
		field_property = one(templates.objects(field, E.property))
		visit_field(templates, f1, f2, template, f1_data, f2_data, field, None, field_property, field_property)

	
def visit_field(templates, f1, f2, template, f1_data, f2_data, field, field_type, f1_field_property, f2_field_property):
	print(f"field: {f1_field_property}")

	f1_field_values = list(f1.objects(f1_data, f1_field_property))
	f2_field_values = list(f2.objects(f2_data, f2_field_property))
	# print(f"record {data} has field: {field_property}")

	if len(f1_field_values) != len(f2_field_values):
		warn(f"unequal number of values: {len(f1_field_values)} vs {len(f2_field_values)}")
		warn(f"{f1_data} has {f1_field_property} values: {f1_field_values}")
		warn(f"{f2_data} has {f2_field_property} values: {f2_field_values}")
		return

	if len(f1_field_values) == 1:
		f1_field_value = f1_field_values[0]
		f2_field_value = f2_field_values[0]

		if field_type is None:
			field_types = list(templates.objects(field, E.type))
			if len(field_types) == 1:
				field_type = field_types[0]
			elif len(field_types) > 1:
				raise ValueError(f"expected one or zero field_type's")
		if field_type is not None:
			visit_discrete_field(templates, f1, f2, field, field_type, f1_field_value, f2_field_value)
		else:
			subrecord_template = one(templates.objects(field, E.template))
			walk_record(templates, f1, f2, subrecord_template, f1_field_value, f2_field_value)
	elif len(f1_field_values) == 0:
		print("no value")
		if len(f2_field_values) != 0:
			warn(f"f2 record {f2_data} field: {f2_field_property} has values: {f2_field_values}, while f1 has no values")
	else:
		raise ValueError(
			f"expected one or zero values, record {data} has field: {field_property} with unexpected number of values: {field_values}")


def visit_discrete_field(templates, f1, f2, field, field_type, f1_field_value, f2_field_value):
	v1 = one(f1.objects(f1_field_value, RDF.value))
	v2 = one(f2.objects(f2_field_value, RDF.value))
	if v1 != v2:
		#warn(f'{type(v1)}, {type(v2)}')
		try:
			if abs(v1.value - v2.value) < 0.0004:
				return True
		except:
			pass
		warn(f"field {field} has different values: {v1} vs {v2}")
		warn(f'{v1.n3()} vs {v2.n3()}')
		print_pos(f1, f1_field_value)
		print_pos(f2, f2_field_value)
	print(f'has value: {v1}')

def print_pos(f, field_value):
	sheet = one(f.objects(field_value, E.has_sheet_name))
	col = one(f.objects(field_value, E.col))
	row = one(f.objects(field_value, E.row))
	warn(f'in {sheet} {col} {row}')


def one(generator):
	l = list(generator)
	if len(l) != 1:
		raise ValueError(f"expected one element, got {len(l)}")
	return l[0]


if __name__ == '__main__':
	compare_sheetsets()

"""
may wanna do 3 rounds, comparing by "server" templates, by fn1 templates, and by fn2 templates.





"""
