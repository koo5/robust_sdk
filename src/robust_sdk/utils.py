from datetime import datetime

from rdflib.collection import Collection
from rdflib import Graph, RDF
from rdflib.term import Literal, BNode, Identifier


def AssertValue(g: Graph, value: any):
	v = BNode()
	g.add((v, RDF.value, value))
	return v

def AssertLiteralValue(g: Graph, value: any):
	v = BNode()
	g.add((v, RDF.value, Literal(value)))
	return v

def AssertListValue(g: Graph, items: list[Identifier]):
	return AssertValue(g, AssertList(g, items))


def AssertList(g, seq: list[Identifier]):
	c = BNode()
	Collection(g, c, seq)
	return c


def date_literal(date_str: str):
	return Literal(datetime.strptime(date_str, '%Y-%m-%d'))

