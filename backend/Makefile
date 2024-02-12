.PHONY: pip-compile
pip-compile:
	pip-compile --quiet --allow-unsafe --strip-extras --generate-hashes --output-file requirements.txt pyproject.toml
	pip-compile --quiet --allow-unsafe --strip-extras --generate-hashes --constraint requirements.txt --extra dev --output-file requirements-dev.txt pyproject.toml

.PHONY: pip-compile-upgrade
pip-compile-upgrade:
	pip-compile --upgrade --quiet --allow-unsafe --strip-extras --generate-hashes --output-file requirements.txt pyproject.toml
	pip-compile --upgrade --quiet --allow-unsafe --strip-extras --generate-hashes --constraint requirements.txt --extra dev --output-file requirements-dev.txt pyproject.toml

.PHONY: pip-sync
pip-sync:
	pip-sync requirements-dev.txt
