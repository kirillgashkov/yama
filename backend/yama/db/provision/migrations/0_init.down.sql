BEGIN;

DROP TABLE IF EXISTS file_ancestors_file_descendants;

DROP TABLE IF EXISTS files;

DROP TABLE IF EXISTS file_types;

DROP TABLE IF EXISTS users;

DROP EXTENSION IF EXISTS "uuid-ossp";

COMMIT;
