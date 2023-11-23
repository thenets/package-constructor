# HELP related targets
#
# This generates one-line help for each target.
# Also usefull to improve documentation and manutenability.
# --------------------------------------
HELP_FILTER=.PHONY
T_COLOR_RED=\033[0;31m
T_COLOR_GREEN=\033[0;32m
T_RESET=\033[0m

# Display help targets
help:
	@printf "Available targets:\n"
	@make -s help-generate | grep -vE "\w($(HELP_FILTER))"

# Generate help output from MAKEFILE_LIST
help-generate:
	@awk '/^[-a-zA-Z_0-9%:\\\.\/]+:/ { \
		helpMessage = match(lastLine, /^## (.*)/); \
		if (helpMessage) { \
			helpCommand = $$1; \
			helpMessage = substr(lastLine, RSTART + 3, RLENGTH); \
			gsub("\\\\", "", helpCommand); \
			gsub(":+$$", "", helpCommand); \
			printf "  \x1b[32;01m%-35s\x1b[0m %s\n", helpCommand, helpMessage; \
		} \
	} \
	{ lastLine = $$0 }' $(MAKEFILE_LIST) | sort -u
	@printf "\n"
