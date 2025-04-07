CREATE TABLE memories (
    id INTEGER PRIMARY KEY NOT NULL,
    time TEXT NOT NULL,
    content TEXT NOT NULL
) STRICT;

CREATE TABLE memory_tags (
    id INTEGER PRIMARY KEY NOT NULL,
    memory_id INTEGER NOT NULL,
    tag TEXT NOT NULL,
    FOREIGN KEY (memory_id) REFERENCES memories(id)
) STRICT;

CREATE TABLE function_calls (
    id INTEGER PRIMARY KEY NOT NULL,
    time TEXT NOT NULL,
    call_id TEXT NOT NULL,
    function_name TEXT NOT NULL,
    function_arguments TEXT NOT NULL
) STRICT;

CREATE TABLE outputs (
    id INTEGER PRIMARY KEY NOT NULL,
    time TEXT NOT NULL,
    content TEXT NOT NULL
) STRICT;
