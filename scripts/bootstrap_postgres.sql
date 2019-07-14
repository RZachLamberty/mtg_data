-- make sure the user exists
DO
$body$
BEGIN
  IF NOT EXISTS (
    SELECT *
    FROM pg_catalog.pg_user
    WHERE usename = 'mtg'
  ) THEN
    CREATE ROLE mtg LOGIN PASSWORD 'mtg';
  END IF;
END
$body$
;

-- create the database
CREATE DATABASE mtg OWNER mtg;

-- connect to the database we just created
\c mtg

-- we will model cards and categories as a table of categories, a table of cards, and a table of relationships
BEGIN;
  CREATE TABLE categories (
    id serial primary key
    , category text
    , parent_id int
  );
COMMIT;

BEGIN;
  CREATE TABLE cards (
    id serial primary key
    , cardname text
  );
  COMMIT;

BEGIN;
  CREATE TABLE usertags (
    tag_id serial
    , category_id int references categories(id)
    , card_id int references cards(id)
  );
COMMIT;

BEGIN;
GRANT ALL PRIVILEGES ON TABLE categories TO mtg;
GRANT ALL PRIVILEGES ON TABLE cards TO mtg;
GRANT ALL PRIVILEGES ON TABLE usertags TO mtg;
COMMIT;
