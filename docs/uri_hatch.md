# URI hatch

For most uses you don't need this. It's the escape hatch for cases where
you want to attach extra RDF triples to the same graph the SDK builds —
typically per-row or per-cell provenance metadata.

## What's exposed

After `build_request_rdf(req)` (or `submit(req, …)`) runs, every domain
model has two fields populated:

| field | what it points at | when set |
|---|---|---|
| `model.uri` | the row entity (subject of the `rdf:type` triple) | always after build; pre-populating pins your own identity |
| `model.cells[field_name]` | the cell-wrapper for each emitted property value | build-output only; populated for every field actually written |

Both fields hold real `rdflib.term.Identifier` instances (`URIRef` for
pre-populated values or for the request envelope, `BNode` for everything
the builder mints itself), so they slot into rdflib triples directly with
no wrapping helper.

`cells` keys are the Python field names, including list-typed fields
(e.g. `bs.cells["transactions"]` is the cell wrapping the RDF Collection
of transactions inside that bank statement). Optional fields appear in
`cells` only when they were actually emitted.

## Attaching extra metadata

```python
from rdflib import Literal, Namespace
from robust_sdk2 import build_request_rdf

graph = build_request_rdf(req)
MY = Namespace("https://my.example/ns#")
txn = req.bank_statements[0].transactions[0]

# Row-level: a fact about the transaction itself.
graph.add((txn.uri, MY.classifier_confidence, Literal(0.94)))

# Cell-level: a fact about the source of one specific value.
graph.add((txn.cells["description"], MY.source_file, Literal("ledger.yaml")))
graph.add((txn.cells["description"], MY.source_line, Literal(42)))
```

The legacy spreadsheet pipeline used the same channel for `excel:col` /
`excel:row` / `excel:has_sheet_name` annotations, but the predicate
shape is up to the caller — attach whatever fits your input source.

## Pinning a stable URI

If you want a stable identifier instead of a fresh blank node — e.g. for
correlation with an external system — pre-populate `uri` before building.
Strings are coerced to `URIRef`; pass a `URIRef` or `BNode` directly to
control the term type.

```python
txn = Transaction(
    uri="https://my.example/txn/2024-08-15-coffee",  # coerced to URIRef
    description="Coffee",
    date=date(2024, 8, 15),
    debit=Decimal("4.50"),
)
build_request_rdf(req)
# txn.uri is now URIRef("https://my.example/txn/2024-08-15-coffee")
# and the same URI is the subject of the description / date / debit triples
```
