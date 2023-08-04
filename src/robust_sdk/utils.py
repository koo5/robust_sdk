from datetime import datetime

from rdflib.collection import Collection
from rdflib import Graph, RDF
from rdflib.term import Literal, BNode, Identifier
from .prefixes import *



def AssertList(g, seq: list[Identifier]):
	c = BNode()
	Collection(g, c, seq)
	return c


def date_literal(date_str: str):
	return Literal(datetime.strptime(date_str, '%Y-%m-%d'))

