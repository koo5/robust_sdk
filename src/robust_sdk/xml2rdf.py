# https://docs.python.org/3/library/xml.etree.elementtree.html
import logging
import pathlib
import xml.etree.ElementTree as xmltree
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

		self.g = rdflib.Graph(identifier = R.data_graph)
		self.rg = rdflib.Graph(identifier = R.request_graph)
		
		self.all_request_sheets = []
		self.unit_names = set()

		self.endDate = self.xml_request.find('endDate').text
		self.startDate = self.xml_request.find('startDate').text

		self.reportCurrency = self.xml_request.find('reportCurrency/unitType').text
		#logging.getLogger('dataDebug').debug(self.defaultCurrency.__repr__())
		#print(self.defaultCurrency)

		self.add_report_details_sheet()
		self.add_bank_statement_sheets()
		self.add_unit_values_sheet()
		self.add_action_verbs_sheet()
		self.add_unit_types_sheet()



		self.rg.add((ER.request, E.has_sheet_instances, AssertList(self.rg, self.all_request_sheets)))
		self.g.add((ER.request, R.client_version, Literal("3")))

		# i think this is "guaranteed" not to produce collisions of bnodes names, since all bnodes are generated by calling BNode(), which uses uuid4()
		merged_graph = self.g + self.rg
		#merged_graph.identifier = R.merged_graph
		#result_file = destdir / 'request.trig'
		result_file = destdir / 'request.n3'
		#merged_graph.serialize(result_file, format='trig')
		merged_graph.serialize(result_file, format='n3')

		return result_file



	def add_report_details_sheet(self):
		report_details = BNode()#'bank_statement')
		self.g.add((report_details, RDF.type, BS.report_details))

		self.g.add((report_details, IC.cost_or_market,	self.assert_value(IC.market)))
		self.g.add((report_details, IC.currency,	self.assert_value(self.xml_request.find('reportCurrency').find('unitType').text)))
		self.g.add((report_details, IC['from'],		self.assert_value(date_literal(self.startDate))))
		self.g.add((report_details, IC['to'],		self.assert_value(date_literal(self.endDate))))
		self.g.add((report_details, IC.pricing_method,	self.assert_value(IC.lifo)))
		
		taxonomy1 = BNode(); self.g.add((taxonomy1, V1['account_taxonomies#url'],  self.assert_value(V1['account_taxonomies#base'])))
		taxonomy2 = BNode(); self.g.add((taxonomy2, V1['account_taxonomies#url'],  self.assert_value(V1['account_taxonomies#investments__legacy'])))
		#taxonomy3 = BNode(); g.add((taxonomy3, V1['account_taxonomies#url'],  V1['account_taxonomies#livestock']))
		account_taxonomies = [
			taxonomy1,
			taxonomy2,
			#self.assert_value(g, taxonomy3)
		]
		self.g.add((report_details, IC_UI.account_taxonomies, self.assert_list_value(account_taxonomies)))
		self.add_sheet(IC_UI.report_details_sheet, 'report_details', report_details)




	def add_bank_statement_sheets(self):

		bst = self.xml_request.find('bankStatement')
		if bst is None:
			raise InputException('Not a valid IC XML file')

		for accd in bst.findall("accountDetails"):
			xml_transactions = accd.find('transactions')
			rdf_transactions = []
			for t in xml_transactions:

				transdesc = t.findtext('transdesc')
				transdate = t.findtext('transdate')
				debit = t.findtext('debit')
				credit = t.findtext('credit')
				unit = t.findtext('unit')
				unitType = t.findtext('unitType')

				#print(transdesc, transdate, debit, credit, unit, unitType)

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
			#print(accountNo, accountName, bankID, currency)

			bs = BNode()#'bank_statement')
			self.g.add((bs, RDF.type, BS.bank_statement))
			self.g.add((bs, BS.account_currency, self.assert_value(currency)))
			self.g.add((bs, BS.account_name, self.assert_value(accountName)))
			self.g.add((bs, BS.account_number, self.assert_value(accountNo)))
			self.g.add((bs, BS.bank_id, self.assert_value(bankID)))
			self.g.add((bs, BS.items, self.assert_list_value(rdf_transactions)))

			self.add_sheet(IC_UI.bank_statement_sheet, accountName, bs)




	def add_unit_values_sheet(self):
		unit_values = []
		for xml_unit_value in self.xml_request.find('unitValues').findall('unitValue'):
			v = BNode()#'unit_value')
			unit_values.append(v)
			unitType = xml_unit_value.find('unitType').text
			unitValue = xml_unit_value.find('unitValue').text
			unitValueDate = xml_unit_value.findtext('unitValueDate')
			if unitValueDate in ['', None]:
				unitValueDate = self.endDate
			elif unitValueDate == 'opening':
				unitValueDate = self.startDate
			elif unitValueDate == 'closing':
				unitValueDate = self.endDate
																						#todo might just as well pass all dates through as text?
			unitValueCurrency = xml_unit_value.findtext('unitValueCurrency')
			if unitValueCurrency in ['', None]:
				unitValueCurrency = self.reportCurrency
			#print(unitType, unitValue, unitValueDate)

			self.g.add((v, RDF.type, IC.unit_value))
			self.g.add((v, UV.name, self.assert_value(unitType)))
			self.g.add((v, UV.value, self.assert_value(unitValue)))
			self.g.add((v, UV.date, self.assert_value(date_literal(unitValueDate))))
			self.g.add((v, UV.currency, self.assert_value(unitValueCurrency)))
			
			self.unit_names.add(unitType)

		self.add_sheet(IC.unit_valueses, 'unit_values', self.assert_list_value(unit_values))




	def add_action_verbs_sheet(self):
		action_verbs = []
		xml_verbs = self.xml_request.findall('actionTaxonomy/action')
		for xml_verb in xml_verbs:
			v = BNode()#'action')
			action_verbs.append(v)
			id = xml_verb.find('id').text
			exchangeAccount = xml_verb.find('exchangeAccount').text
			tradingAccount = xml_verb.findtext('tradingAccount')
			description = xml_verb.findtext('description')

			self.g.add((v, RDF.type, IC.action_verb))
			self.g.add((v, AV.name, self.assert_value(id)))
			if description not in [None, '']:
				self.g.add((v, AV.description, self.assert_value(description)))
			self.g.add((v, AV.exchanged_account, self.assert_value(exchangeAccount)))
			if tradingAccount not in [None, '']:
				self.g.add((v, AV.trading_account, self.assert_value(tradingAccount)))


		self.add_sheet(IC_UI.action_verbs_sheet, 'action_verbs', self.assert_list_value(action_verbs))



	def add_sheet(self, sheet_type: Identifier, name: str, record: Identifier):
		sheet_instance = BNode()#'sheet_instance')
		self.rg.add((sheet_instance, E.sheet_instance_has_sheet_type, sheet_type))
		self.rg.add((sheet_instance, E.sheet_instance_has_sheet_name, Literal(name)))
		self.rg.add((sheet_instance, E.sheet_instance_has_sheet_data, record))
		self.all_request_sheets.append(sheet_instance)


	def assert_value(self, value: any):
		v = BNode()
		if not isinstance(value, Identifier):
			value = Literal(value)
		self.g.add((v, RDF.value, value))
		self.rg.add((v, E.sheet_name, Literal('unknown')))
		return v

	def assert_list_value(self, items: list[Identifier]):
		return self.assert_value(AssertList(self.g, items))

	def add_unit_types_sheet(self):
		types = []
		for name in self.unit_names:
			u = BNode()
			self.g.add((u, IC.unit_type_name, self.assert_value(name)))
			self.g.add((u, IC.unit_type_category, self.assert_value('Financial_Investments')))
			types.append(u)

		self.add_sheet(IC_UI.unit_types_sheet, 'unit_types', self.assert_list_value(types))



class InputException(Exception):
	pass

