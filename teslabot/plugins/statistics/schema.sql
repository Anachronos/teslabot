-- Channel tables

CREATE TABLE channel (
	id INTEGER PRIMARY KEY,
	name TEXT
);

CREATE TABLE channel_visit (
	id INTEGER PRIMARY KEY,
	cid INTEGER,
	count INTEGER,
	time INTEGER,
	FOREIGN KEY(cid) REFERENCES channel(id)
);

CREATE TABLE channel_quote (
	id INTEGER PRIMARY KEY,
	cid INTEGER,
	user TEXT,
	quote TEXT,
	FOREIGN KEY(cid) REFERENCES channel(id)
);

CREATE TABLE word_list (
	id INTEGER PRIMARY KEY,
	cid INTEGER,
	word TEXT,
	count INTEGER,
	FOREIGN KEY(cid) REFERENCES channel(id)
);

CREATE TABLE user (
	id INTEGER PRIMARY KEY,
	nick TEXT,
	lastseen_time INT,
	lastseen_cid INT,
	FOREIGN KEY(lastseen_cid) REFERENCES channel(id)
);

CREATE TABLE user_statistics (
	cid INTEGER,
	uid INTEGER,
	word_count INTEGER,
	line_count INTEGER,
	FOREIGN KEY(uid) REFERENCES user(id),
	FOREIGN KEY(cid) REFERENCES channel(id)
);