import click
import cli_server
import cli_builder


# main
# --------------------
if __name__ == "__main__":

    @click.group()
    def cli():
        pass

    cli_server.click_add_group(cli)
    cli_builder.click_add_group(cli)
    # TODO migrate "nexus" group
    # TODO migrate "request" group

    cli()
