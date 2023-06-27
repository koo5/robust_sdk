import click



@click.command()
@click.option('--xml', help='Legacy ROBUST IC XML file.')

def xml2rdf(count, name):
	"""Simple program that greets NAME for a total of COUNT times."""
	for x in range(count):
		click.echo(f"Hello {name}!")

if __name__ == '__main__':
	hello()
	
	