import functools
import click
from .xml2rdf import Xml2rdf

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
@click.group(context_settings=CONTEXT_SETTINGS)
@click.option('--debug/--no-debug', default=False)
def cli(debug):
    click.echo(f"Debug mode is {'on' if debug else 'off'}")

@cli.command()
@click.argument('xml', type=click.File('r'))
@functools.wraps(xml2rdf)
def xml2rdf(xml, destdir='.'):
	return Xml2rdf().xml2rdf(xml, destdir)


if __name__ == '__main__':
	cli()



