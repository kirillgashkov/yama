# Yama

The backend server is a FastAPI application with a modular architecture inspired
by Go.

Noteworthy modules:

- [`api`](yama/api) is responsible for the FastAPI application itself.

  It collects routes from other modules and manages application's lifetime
  dependencies, such as the database engine and module settings. 

- [`database`](yama/database) provides other modules with database connections.

- [`database/provision`](yama/database/provision) provisions the Postgres
  database.

  It uses [golang-migrate](https://github.com/golang-migrate/migrate) for
  database migrations.

- [`auth`](yama/auth) provides user authorization based on OAuth2.

  It supports password and refresh token grants and has an ability to revoke an
  issued refresh token.

- [`user`](yama/user) manages users.

- [`file`](yama/file) manages a virtual file system for notes.

  The system is implemented from scratch and optimized for read operations. It
  utilizes a database to store its file tree and disk storage for file content.
  It features a simplified access control system similar to Google Drive,
  enabling users to share files with others instead of having rigid ownership
  structures. See [#13](https://github.com/kirillgashkov/yama/pull/13) for
  details.

- [`function`](yama/function) executes *functions* on notes.

  A function is a (potentially) external program that operates on Markdown
  files. The external program could be vulnerable and untrusted, and so are the
  Markdown files. To get out of this pickle the functions are executed in a
  safe environment using Docker to keep them isolated from the application.

  For now this module can execute the import and export functions. These
  functions are implemented as separate modules and described below.

- [`import_`](yama/import_) takes a Microsoft Word document and converts it to
  Markdown using [Pandoc](https://pandoc.org/).

- [`export`](yama/export) takes a Markdown document and converts it to PDF using
  [Pandoc](https://pandoc.org/) and [LaTeX](https://www.latex-project.org/).

## Installation and Running

### Docker Compose

Clone the repository, change to its directory, then run:

```sh
$ docker compose up -d
```

Go to `http://localhost:8000/docs` to explore the API.

### Manual

Clone the repository, change to its directory, create a new virtual environment,
set environment variables, then run:

```sh
$ source /path/to/venv/bin/activate
$ pip install pip-tools
$ make pip-sync
$ python -m yama api
```

Go to `http://localhost:8000/docs` to explore the API.
