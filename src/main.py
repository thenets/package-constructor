import click

import cli_builder
import cli_nexus
import cli_pip
import cli_server

# main
# --------------------
if __name__ == "__main__":

    @click.group()
    def cli():
        pass

    cli_server.click_add_group(cli)
    cli_builder.click_add_group(cli)
    cli_nexus.click_add_group(cli)
    cli_pip.click_add_group(cli)
    # TODO migrate "cachito" group

    cli()
