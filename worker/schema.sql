CREATE TABLE IF NOT EXISTS tasks (
 id TEXT PRIMARY KEY, author TEXT NOT NULL, created TEXT NOT NULL, request TEXT NOT NULL,
 page TEXT NOT NULL, spec TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
 reviewer TEXT, reviewed TEXT, attempt INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS attempts (
 task TEXT NOT NULL, n INTEGER NOT NULL, stage TEXT NOT NULL DEFAULT '排队中',
 log TEXT NOT NULL DEFAULT '', url TEXT, touched INTEGER NOT NULL DEFAULT 0,
 run TEXT, PRIMARY KEY(task,n)
);
CREATE TRIGGER IF NOT EXISTS start_attempt AFTER UPDATE OF attempt ON tasks
WHEN NEW.attempt>OLD.attempt BEGIN
 INSERT INTO attempts(task,n) VALUES(NEW.id,NEW.attempt);
END;
CREATE TABLE IF NOT EXISTS collection_batches (
 task TEXT NOT NULL, batch INTEGER NOT NULL, items TEXT NOT NULL, PRIMARY KEY(task,batch)
);
CREATE INDEX IF NOT EXISTS task_status ON tasks(status,created);
