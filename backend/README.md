# Yama

The backend server is a FastAPI application with a modular architecture inspired
by Netflix's [dispatch](https://github.com/Netflix/dispatch). Each module has a
consistent and straightforward structure:

- `routes.py` for FastAPI routes.
- `dependencies.py` for FastAPI dependencies.
- `utils.py` for *utility* functions (also collectively known as a service,
  these shouldn't be confused with helper functions, these are functions with
  exposed module-specific business logic that can be used by other modules).
- `models.py` for SQLAlchemy and Pydantic models.
- `settings.py` for settings.

<blockquote>
<details>
  <summary>Why <code>utils.py</code> and not <code>service.py</code>?</summary>

  Taste. And a bit of inspiration by
  <a href="https://tailwindcss.com/">Tailwind's</a> usage of the word "utility".
  Besides, generally it's not a good idea to have random <code>utils.py</code>
  with generic helper functions all over your project anyways.
</details>
</blockquote>

Noteworthy modules:

- [`api`](yama/api) is responsible for the FastAPI application itself.

  It collects routes from other modules and manages application's lifetime
  dependencies, such as the database engine and module settings. 

- [`database`](yama/database) provides other modules with database connections.

- [`database/provision`](yama/database/provision) provisions the Postgres database.

  It uses [`golang-migrate`](https://github.com/golang-migrate/migrate) for database migrations.

- [`user`](yama/user) manages users.

- [`user/auth`](yama/user/auth) provides user authorization based on OAuth2.

  It supports password and refresh token grants and has an ability to revoke an
  issued refresh token.

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
  Markdown files. To get out of this pickle the functions are executed in a safe
  environment using Docker to keep them isolated from the application.

- [`function/import_`](yama/function/import_) implements the import function
  that accepts a Microsoft Word document and converts it to Markdown using
  [Pandoc](https://pandoc.org/).

- [`function/export`](yama/function/export) implements the export function that
  accepts a Markdown document and converts it to PDF using
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
