import click
import cli_server
import cli_builder
import cli_nexus


# main
# --------------------
if __name__ == "__main__":

    @click.group()
    def cli():
        pass

    cli_server.click_add_group(cli)
    cli_builder.click_add_group(cli)
    cli_nexus.click_add_group(cli)
    # TODO migrate "request" group

    cli()
