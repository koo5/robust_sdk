import click

# https://docs.python.org/3/library/xml.etree.elementtree.html
import xml.etree.ElementTree as xmltree



@click.group()
@click.option('--debug/--no-debug', default=False)
def cli(debug):
    click.echo(f"Debug mode is {'on' if debug else 'off'}")

@cli.command()  # @cli, not @click!
@click.option('--xml', help='Legacy ROBUST IC XML file.')
def xml2rdf(xml):
	"""Load the XML IC file and produce robust IC RDF"""
	x = xmltree.parse(xml).getroot()
	print(x)


if __name__ == '__main__':
	cli()
	
	