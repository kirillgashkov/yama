BEGIN;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS user_types (
    type varchar NOT NULL,
    PRIMARY KEY (type)
);
INSERT INTO user_types (type) VALUES ('regular'), ('group');

CREATE TABLE IF NOT EXISTS users (
    id uuid NOT NULL DEFAULT uuid_generate_v4(),
    type varchar NOT NULL,
    handle varchar NOT NULL,
    password_hash varchar,
    PRIMARY KEY (id),
    FOREIGN KEY (type) REFERENCES user_types (type)
);

CREATE TABLE IF NOT EXISTS user_ancestors_user_descendants (
    id uuid NOT NULL DEFAULT uuid_generate_v4(),
    ancestor_id uuid NOT NULL,
    descendant_id uuid NOT NULL,
    descendant_depth integer NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (ancestor_id) REFERENCES users (id),
    FOREIGN KEY (descendant_id) REFERENCES users (id)
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
    id uuid NOT NULL DEFAULT uuid_generate_v4(),
    ancestor_id uuid NOT NULL,
    descendant_id uuid NOT NULL,
    descendant_path varchar NOT NULL,
    descendant_depth integer NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (ancestor_id) REFERENCES files (id),
    FOREIGN KEY (descendant_id) REFERENCES files (id)
);
CREATE UNIQUE INDEX fafd_parent_id_child_name_uidx
    ON file_ancestors_file_descendants (ancestor_id, descendant_path)
    WHERE descendant_depth = 1;

CREATE TABLE IF NOT EXISTS file_share_types (
    type varchar NOT NULL,
    PRIMARY KEY (type)
);
INSERT INTO file_share_types (type) VALUES ('read'), ('write'), ('share');

CREATE TABLE IF NOT EXISTS file_shares (
    id uuid NOT NULL DEFAULT uuid_generate_v4(),
    type varchar NOT NULL,
    file_id uuid NOT NULL,
    user_id uuid NOT NULL,
    created_by uuid NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (type) REFERENCES file_share_types (type),
    FOREIGN KEY (file_id) REFERENCES files (id),
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (created_by) REFERENCES users (id)
);

COMMIT;
