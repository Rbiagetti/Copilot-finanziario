CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount REAL NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    note TEXT,
    source TEXT NOT NULL DEFAULT 'manual'
);
