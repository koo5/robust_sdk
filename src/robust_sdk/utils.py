from rdflib import Graph, RDF
from rdflib.term import Literal, BNode, Identifier


def AssertValue(g: Graph, value: any):
    v = BNode()
    g.add(v, RDF.value, Literal(value))
    return v