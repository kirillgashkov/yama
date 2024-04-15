BEGIN;

DROP TABLE IF EXISTS file_shares;

DROP TABLE IF EXISTS file_share_types;

DROP TABLE IF EXISTS file_ancestors_file_descendants;

DROP TABLE IF EXISTS files;

DROP TABLE IF EXISTS file_types;

DROP TABLE IF EXISTS user_ancestors_user_descendants;

DROP TABLE IF EXISTS users;

DROP TABLE IF EXISTS user_types;

DROP EXTENSION IF EXISTS "uuid-ossp";

COMMIT;
