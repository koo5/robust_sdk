# https://docs.python.org/3/library/xml.etree.elementtree.html
import pathlib
import xml.etree.ElementTree as xmltree
from pymaybe import maybe
import rdflib
from rdflib.term import Literal, BNode, Identifier
from .utils import *
from .prefixes import *





class Xml2rdf():

	def xml2rdf(self, xml, destdir: pathlib.Path):
		"""
		Load the legacy IC XML file and produce robust IC RDF.
		XML - path of XML file.
		"""
		self.xml_request = xmltree.parse(xml).getroot().find('balanceSheetRequest')
		if self.xml_request is None:
			raise InputException('Not a valid IC XML file')

		self.g = rdflib.Graph()
		self.rg = rdflib.Graph(identifier = R.request_graph)
		self.reportCurrency = None
		self.endDate = None
		self.all_request_sheets = []

		self.defaultCurrency = self.xml_request.find('defaultCurrency').text

		self.add_report_details_sheet()
		self.add_bank_statement_sheets()
		self.add_unit_values_sheet()
		self.add_action_verbs_sheet()

		self.rg.add((ER.request, E.has_sheet_instances, AssertList(self.rg, self.all_request_sheets)))
		self.g.add((ER.request, R.client_version, Literal("3")))

		# i think this is guaranteed not to produce collisions of bnodes names, since all bnodes are generated by calling BNode(), which uses uuid4()
		result_graph = self.g + self.rg
		result_file = destdir / 'result.trig'
		result_graph.serialize(result_file, format='trig')

		# print()
		# print('vvvv')
		# print(result_graph.serialize(format='turtle'))
		# print('^^^^')
		# print()
		return result_file



	def add_report_details_sheet(self):
		report_details = BNode()#'bank_statement')
		self.g.add((report_details, RDF.type, BS.report_details))

		self.g.add((report_details, IC.cost_or_market,		AssertValue(self.g, IC.market)))
		self.g.add((report_details, IC.currency,			AssertLiteralValue(self.g, self.xml_request.find('reportCurrency').find('unitType').text)))
		self.g.add((report_details, IC['from'],				AssertValue(self.g, date_literal(self.xml_request.find('startDate').text))))
		self.g.add((report_details, IC['to'],				AssertValue(self.g, date_literal(self.xml_request.find('endDate').text))))
		self.g.add((report_details, IC.pricing_method,		AssertValue(self.g, IC.lifo)))

		taxonomy1 = BNode(); self.g.add((taxonomy1, V1['account_taxonomies#url'],  V1['account_taxonomies#base']))
		taxonomy2 = BNode(); self.g.add((taxonomy2, V1['account_taxonomies#url'],  V1['account_taxonomies#investments']))
		#taxonomy3 = BNode(); g.add((taxonomy3, V1['account_taxonomies#url'],  V1['account_taxonomies#livestock']))
		account_taxonomies = [
			AssertValue(self.g, taxonomy1),
			AssertValue(self.g, taxonomy2),
			#AssertValue(g, taxonomy3)
		]
		self.g.add((report_details, IC_UI.account_taxonomies, AssertListValue(self.g, account_taxonomies)))
		self.add_sheet(IC_UI.report_details_sheet, 'report_details', report_details)




	def add_bank_statement_sheets(self):

		bst = self.xml_request.find('bankStatement')
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
				self.g.add((tx, R.transaction_has_description, Literal(transdesc)))
				self.g.add((tx, R.transaction_has_date, Literal(transdate)))
				self.g.add((tx, R.transaction_has_debit, Literal(debit)))
				self.g.add((tx, R.transaction_has_credit, Literal(credit)))
				self.g.add((tx, R.transaction_has_unit, Literal(unit)))
				self.g.add((tx, R.transaction_has_unit_type, Literal(unitType)))

			accountNo = accd.find('accountNo').text
			accountName = accd.find('accountName').text
			bankID = accd.find('bankID').text
			currency = accd.find('currency').text
			print(accountNo, accountName, bankID, currency)

			bs = BNode()#'bank_statement')
			self.g.add((bs, RDF.type, BS.bank_statement))
			self.g.add((bs, BS.account_currency, AssertLiteralValue(self.g, currency)))
			self.g.add((bs, BS.account_name, AssertLiteralValue(self.g, accountName)))
			self.g.add((bs, BS.account_number, AssertLiteralValue(self.g, accountNo)))
			self.g.add((bs, BS.bank_id, AssertLiteralValue(self.g, bankID)))
			self.g.add((bs, BS.items, AssertListValue(self.g, rdf_transactions)))

			self.add_sheet(IC_UI.bank_statement_sheet, accountName, bs)




	def add_unit_values_sheet(self):
		unit_values = []
		for xml_unit_value in self.xml_request.find('unitValues').findall('unitValue'):
			v = BNode()#'unit_value')
			unit_values.append(v)
			unitType = xml_unit_value.find('unitType').text
			unitValue = xml_unit_value.find('unitValue').text
			unitValueDate = maybe(xml_unit_value.find('unitValueDate')).text
			if unitValueDate in ['', None]:
				unitValueDate = self.endDate
			unitValueCurrency = xml_unit_value.find('unitValueCurrency').text
			if unitValueCurrency == '':
				unitValueCurrency = self.reportCurrency
			print(unitType, unitValue, unitValueDate)

			self.g.add((v, RDF.type, IC.unit_value))
			self.g.add((v, UV.name, AssertLiteralValue(self.g, unitType)))
			self.g.add((v, UV.value, AssertLiteralValue(self.g, unitValue)))
			self.g.add((v, UV.date, AssertValue(self.g, date_literal(unitValueDate))))
			self.g.add((v, UV.currency, AssertLiteralValue(self.g, unitValueCurrency)))

		self.add_sheet(IC_UI.unit_values_sheet, 'unit_values', AssertListValue(self.g, unit_values))




	def add_action_verbs_sheet(self):
		action_verbs = []
		xml_verbs = self.xml_request.findall('actionTaxonomy/action')
		for xml_verb in xml_verbs:
			v = BNode()#'action')
			action_verbs.append(v)
			id = xml_verb.find('id').text
			exchangeAccount = xml_verb.find('exchangeAccount').text
			tradingAccount = xml_verb.find('tradingAccount').text
			description = xml_verb.find('description').text

			self.g.add((v, RDF.type, IC.action_verb))
			self.g.add((v, AV.name, AssertLiteralValue(self.g, id)))
			self.g.add((v, AV.description, AssertLiteralValue(self.g, description)))
			self.g.add((v, AV.exchanged_account, AssertLiteralValue(self.g, exchangeAccount)))
			self.g.add((v, AV.trading_account, AssertLiteralValue(self.g, tradingAccount)))


		self.add_sheet(IC_UI.action_verbs_sheet, 'action_verbs', AssertListValue(self.g, action_verbs))



	def add_sheet(self, sheet_type: Identifier, name: str, record: Identifier):
		sheet_instance = BNode()#'sheet_instance')
		self.rg.add((sheet_instance, E.sheet_instance_has_sheet_type, sheet_type))
		self.rg.add((sheet_instance, E.sheet_instance_has_sheet_name, Literal(name)))
		self.rg.add((sheet_instance, E.sheet_instance_has_sheet_data, record))
		self.all_request_sheets.append(sheet_instance)




class InputException(Exception):
	pass

