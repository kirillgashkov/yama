BEGIN;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS users (
    id uuid NOT NULL DEFAULT uuid_generate_v4(),
    username varchar NOT NULL,
    password_hash varchar NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS file_types (
    type varchar NOT NULL,
    PRIMARY KEY (type)
);
INSERT INTO file_types (type) VALUES ('regular'), ('directory');

CREATE TABLE IF NOT EXISTS files (
    id uuid NOT NULL DEFAULT uuid_generate_v4(),
    type varchar NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (type) REFERENCES file_types (type)
);

CREATE TABLE IF NOT EXISTS file_ancestors_file_descendants (
    ancestor_id uuid NOT NULL,
    descendant_id uuid NOT NULL,
    descendant_path varchar NOT NULL,
    depth integer NOT NULL,
    PRIMARY KEY (ancestor_id, descendant_id),
    FOREIGN KEY (ancestor_id) REFERENCES files (id),
    FOREIGN KEY (descendant_id) REFERENCES files (id)
);

COMMIT;
