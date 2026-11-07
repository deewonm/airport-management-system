-- CrewOps database schema (SQLite), simplified
-- Run with:   sqlite3 app.db < schema.sql
-- Times are TEXT in UTC ISO-8601, e.g. '2026-11-07T06:00:00Z'.
-- shiftDate is the airport's local date, e.g. '2026-11-07'.
-- True/false values are INTEGER 0 or 1.
-- Any column ending in "userID" points to users.id, not the 9-digit employee_id.

DROP TABLE IF EXISTS airports;
DROP TABLE IF EXISTS teams;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS skills;
DROP TABLE IF EXISTS userSkills;
DROP TABLE IF EXISTS shifts;
DROP TABLE IF EXISTS shiftAssignments;
DROP TABLE IF EXISTS flights;
DROP TABLE IF EXISTS absenceReports;
DROP TABLE IF EXISTS reassignmentRequests;
DROP TABLE IF EXISTS notifications;

CREATE TABLE airports (
    airportCode TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    timezone    TEXT NOT NULL
);

CREATE TABLE teams (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    airportCode TEXT NOT NULL REFERENCES airports(airportCode),
    name        TEXT NOT NULL,
    UNIQUE (airportCode, name)
);

CREATE TABLE users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    airportCode TEXT NOT NULL REFERENCES airports(airportCode),
    employee_id  INTEGER NOT NULL,
    password    TEXT NOT NULL,
    role        TEXT NOT NULL,
    isAdmin     INTEGER NOT NULL DEFAULT 0,
    firstName   TEXT NOT NULL,
    lastName    TEXT NOT NULL,
    teamID      INTEGER REFERENCES teams(id),
    isActive    INTEGER NOT NULL DEFAULT 1,
    createdAt   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (airportCode, employee_id)
);

CREATE TABLE skills (
    name TEXT PRIMARY KEY
);

CREATE TABLE userSkills (
    userID INTEGER NOT NULL REFERENCES users(id),
    skill  TEXT NOT NULL REFERENCES skills(name),
    PRIMARY KEY (userID, skill)
);

CREATE TABLE shifts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    airportCode TEXT NOT NULL REFERENCES airports(airportCode),
    teamID      INTEGER NOT NULL REFERENCES teams(id),
    shiftDate   TEXT NOT NULL,
    startTime   TEXT NOT NULL,
    endTime     TEXT NOT NULL
);

CREATE TABLE shiftAssignments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    shiftID         INTEGER NOT NULL REFERENCES shifts(id),
    userID          INTEGER NOT NULL REFERENCES users(id),
    coveringSkill   TEXT REFERENCES skills(name),
    status          TEXT NOT NULL DEFAULT 'ready',   -- ready, delayed, sick
    expectedArrival TEXT,
    UNIQUE (shiftID, userID)
);

CREATE TABLE flights (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    airportCode        TEXT NOT NULL REFERENCES airports(airportCode),
    teamID             INTEGER REFERENCES teams(id),
    flightNumber       TEXT NOT NULL,
    airline            TEXT NOT NULL,
    origin             TEXT NOT NULL,
    scheduledArrival   TEXT NOT NULL,
    scheduledDeparture TEXT NOT NULL,
    stand              TEXT,
    status             TEXT NOT NULL DEFAULT 'on_time',  -- on_time, delayed, arrived, departed, cancelled
    approved           INTEGER NOT NULL DEFAULT 0       -- 1 once a supervisor approves the team for this flight
);

CREATE TABLE absenceReports (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    shiftAssignmentID INTEGER NOT NULL UNIQUE REFERENCES shiftAssignments(id),
    reportedAt        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE reassignmentRequests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    absenceReportID INTEGER NOT NULL REFERENCES absenceReports(id),
    proposedUserID  INTEGER REFERENCES users(id),
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending, approved, rejected
    decidedBy       INTEGER REFERENCES users(id),
    decidedAt       TEXT,
    createdAt       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE notifications (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    userID    INTEGER NOT NULL REFERENCES users(id),
    message   TEXT NOT NULL,
    isRead    INTEGER NOT NULL DEFAULT 0,
    createdAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO skills (name) VALUES ('Tug'), ('Belt loader'), ('Baggage'), ('Steps');


-- ---------------------------------------------------------------
-- Sample data
--   * Every account below has the password:  Corkathon2026
--   * Log in with airport code + employee ID. Supervisors (admins) have IDs ending in 400.
--   * Shift dates and flight times are generated for the day this script is run
--     (UTC date). Run the whole file again to refresh the data for a new day.
-- ---------------------------------------------------------------
INSERT INTO airports (airportCode, name, timezone) VALUES
    ('DUB', 'Dublin Airport', 'Europe/Dublin'),
    ('ORK', 'Cork Airport', 'Europe/Dublin');
INSERT INTO teams (id, airportCode, name) VALUES
    (1, 'DUB', 'Team 1'),
    (2, 'DUB', 'Team 2'),
    (3, 'DUB', 'Team 3'),
    (4, 'DUB', 'Team 4'),
    (5, 'ORK', 'Team 1'),
    (6, 'ORK', 'Team 2');
INSERT INTO users (id, airportCode, employee_id, password, role, isAdmin, firstName, lastName, teamID) VALUES
    (1, 'DUB', 482910400, 'scrypt:32768:8:1$vAvN7wn9jpIlOcPp$4664b4c4acb9ec6eb02b72053ac0ba852979c17909c597354fb5156fc880fab684a90fc08be9addbac375d18face3a815ba4651b793c0dfc98e406684820437d', 'supervisor', 1, 'Siobhan', 'Doyle', NULL),
    (2, 'DUB', 482910215, 'scrypt:32768:8:1$PxYFDtnW46r8FFWB$155148d916bc53a6f8ccb9d8e68c9e7910568f96f859012bc6bc6649267b0086abcdba8fce61524ad8b22db26389cb880ec442a80d4c3631eb9a833b40b9e805', 'manager', 0, 'Declan', 'Murphy', NULL),
    (3, 'DUB', 482910301, 'scrypt:32768:8:1$qkIf0n2VFKLPdCPm$c75e0cccaee387ee90ff2a6fc01dd030eab276838c5aeb5c7d3245a836444d698a5797ecccaf370c8fc3857cc1713f3bc84912a6aee739e0e5168d6a3c0dae9c', 'team_leader', 0, 'Aoife', 'Brennan', 1),
    (4, 'DUB', 482910302, 'scrypt:32768:8:1$SuKo3iGMpkfXgzSy$6ad2e9804354f635d6953f4cc0c775587727153f8b3fabcda97a3d9d969fde9c7e458a5f90277f3de4736cfea08b0d9022e61d9125c48cfae98b204056465453', 'team_leader', 0, 'Conor', 'Walsh', 2),
    (5, 'DUB', 482910303, 'scrypt:32768:8:1$hT1WoF2LBPU6IfyG$4bb42a5a19222d60db7100656e5a8b0c516809ed28d42f7df79245496286d87d9058e8f81f82d13c14ead298bf3123edf40c529ab7e616cfda54ca20a5865309', 'team_leader', 0, 'Niamh', 'Byrne', 3),
    (6, 'DUB', 482910304, 'scrypt:32768:8:1$HZ82T278w92pnVtx$da55fa6f1bf556397b5444ba688b1be72381b3dc4e555e94fc29c19c0037ed38554ee0a61ec45d7ef790f45c0ff473e5bab53d81dd18ea3a3d3159ed861ec1f3', 'team_leader', 0, 'Eoin', 'Gallagher', 4),
    (7, 'DUB', 482910311, 'scrypt:32768:8:1$bLrI5BX46969IoOS$43bc5c07ec84edc8dafc4d0f0e3ed98f034801f60eef9327513cbf562571f1522829047562d1829260dd5792fa783355ce9d56ede2d53804b3b3f9e8b59c5524', 'ramp_agent', 0, 'Ciara', 'Kelly', 1),
    (8, 'DUB', 482910312, 'scrypt:32768:8:1$GziWv9XVxCItsliR$bc8180ed00de498cefe1b7183e0c1b836fdf842c42aded5dc67f13cde274df9ea266212fabb47e2658dd39811c9afcf473bd9a7bcfa5705dbd0a5ca69cbd38d9', 'ramp_agent', 0, 'Darragh', 'Ryan', 1),
    (9, 'DUB', 482910313, 'scrypt:32768:8:1$9bSo0xjFJN6ZId63$1118c19ebe89f6f23c309a157396ffb5013d077b3e7fb4fc11686c8245427b178ceda685bfb835d244c86158e54c42b0e9672e9019c56cf2569e428df872e40d', 'ramp_agent', 0, 'Sinead', 'Daly', 1),
    (10, 'DUB', 482910314, 'scrypt:32768:8:1$nL2lNLg1N6GqtnCq$3068470844b68e4b49887ac3c90e267bf6df9154027fd0fbeb42e23770dcf555207ca18ee7615da4c31745bdb0c2b38bf0a7e8c65440e6705258e7f10a570bd3', 'ramp_agent', 0, 'Liam', 'Connor', 2),
    (11, 'DUB', 482910315, 'scrypt:32768:8:1$KD5t7IHv76L0EsVz$13fd478e74d4600504413014fc95aa6900e14d92a9e25d623539039e9c4ba6d0d6148455964842579e1522017cd87703f7589704bc953ca97aafe36611f290ea', 'ramp_agent', 0, 'Roisin', 'Nolan', 2),
    (12, 'DUB', 482910316, 'scrypt:32768:8:1$lVE29G4IFzS68t8g$c08a9fa68e49db4ecffa26602842f20b0b71ce30277517151191ecc12bfa87517846a73da90103bb1a25ffaa69e8a33736035e0f68d0dada25d8ce82d3d7ee6a', 'ramp_agent', 0, 'Cathal', 'Burke', 2),
    (13, 'DUB', 482910317, 'scrypt:32768:8:1$Ev9M1gcwF4o6R9Ad$eb4c0c1f00bed5634c695418ee3e236cec782cab512e10b047326626c138ac6f77cd66d81f76ed7d76c69fbd57e929077a64e8f35f58a1f4ed759c00e3573d69', 'ramp_agent', 0, 'Orla', 'Fitzgerald', 3),
    (14, 'DUB', 482910318, 'scrypt:32768:8:1$3vWZSWmlXh6irfEo$ca23fe57c65ddea69d65ebf975625bb50c1bc72c7b2696b00fe4e79db06a8009fe4c73d3141ec4bdb18ae66e6c1b12a57d64b7c5ea0da785a0272884da2f5df1', 'ramp_agent', 0, 'Sean', 'Maguire', 3),
    (15, 'DUB', 482910319, 'scrypt:32768:8:1$CeSd5JoCCxjkHOEx$8a23afe832bf0eb770bc8237438c8a883b585829920fb433217399932f27c9dc3b8c16bd0de043b17e0e710ab0461aad49b986b3bac61553d314307e99447d79', 'ramp_agent', 0, 'Grace', 'Hennessy', 3),
    (16, 'DUB', 482910320, 'scrypt:32768:8:1$Wl5GYPXA5DjPxl9G$33500b13b70cbb2082bf931e8c41582edbbf38171adc35701ed47f55be20e1891287c0327f64f28aa6f1eca2d11642c243f3bf87b07846d61bcbfff3ebc9f773', 'ramp_agent', 0, 'Tadhg', 'Lynch', 4),
    (17, 'DUB', 482910321, 'scrypt:32768:8:1$25iL4njUd54r7Yj1$6d4da77ae6e4e6deccd3726b712e1d186958f9d77b579a4e552364991ac4adfbe99dec01ca3559d6cc726b1645501cef036cd0321177863968aa603e236392ba', 'ramp_agent', 0, 'Muireann', 'Casey', 4),
    (18, 'DUB', 482910322, 'scrypt:32768:8:1$ije32eneaJaRkw0v$4375d4471bbd5662552240365ac01719d0b8827c497d7edce8b2c899f940e4e2ad97b2a80d82cf6e1c63307bc0c08874cf41efaa87032dbbe67c842646053051', 'ramp_agent', 0, 'Ronan', 'Doherty', 4),
    (19, 'DUB', 482910331, 'scrypt:32768:8:1$3mc2tctYS7rhCOsa$9a0b501f044aba9ef589da5df6c8d7b8bca76be9f37c68d1f8893ebe420e1a88c9363bffb5bc342159591d7db80fe5e5d7b8db491aed6c5bcfaceeba44755e07', 'ramp_agent', 0, 'Fionn', 'Brady', NULL),
    (20, 'DUB', 482910332, 'scrypt:32768:8:1$tyl4OwRlmDAXtUz9$39273b786fb82886f82b717fa61fa53d99aeff8e2ff7401f27f059a1f20e7982280bb17ff09a2a8c4045d902ecdad4e884fb4ddc338c973f0bb131b913864d0d', 'ramp_agent', 0, 'Maeve', 'Clarke', NULL),
    (21, 'DUB', 482910333, 'scrypt:32768:8:1$U4Nh2tCuoKMmh6Cf$6c0540bf0db0a0be80bf38f5023de73286d4ad8eb72e2dd4c773700fe6983eb68a4679f6289733ee861de02132467908328002628d9024c939b3f26e2dda010b', 'ramp_agent', 0, 'Padraig', 'Moran', NULL),
    (22, 'ORK', 517330400, 'scrypt:32768:8:1$sNOFaQSM68tnIEg2$2cc8bc248bcfd12a21909762ac9b2f2e7266c62506bb342809deaa1df5e51214ff0f934fa4bc09f9615f512742cef90d97de8bec4fe57ab64f4cba9a9d2a86d0', 'supervisor', 1, 'Hannah', 'Cotter', NULL),
    (23, 'ORK', 517330301, 'scrypt:32768:8:1$SS0IAR5daWNJUfUd$12668f880ce8258de62fed486e182968624e06ac6fd9bdf9e738ebeae853c3ddf4ae5c08e6718fb15a978f68c6d0c2de187944bd53de5b43a6ed07f061f0bcff', 'team_leader', 0, 'Brian', 'Hegarty', 5),
    (24, 'ORK', 517330302, 'scrypt:32768:8:1$XgRAVQjPDPRHuLtN$1ae1865e4b9fdcd2ce371701a39985fa5879b5b92616bf997f7f5f5c1edf2f0e2b7442256638dc85383a699c6ac92698cee35e8f869d13c2495f2ff9c9099139', 'team_leader', 0, 'Katie', 'Twomey', 6),
    (25, 'ORK', 517330311, 'scrypt:32768:8:1$xdjYwggZO6AMN6o5$548043f12d36bb23b3a6379fe4eb94d56e5ad8d489a3e0e8a004fa2abfbbb7dc3c61c3c62694ab6cd3021a1f6bd983feb4a8da9883f0c3fe77c3a4044bc374a6', 'ramp_agent', 0, 'Jack', 'Crowley', 5),
    (26, 'ORK', 517330312, 'scrypt:32768:8:1$5lI7HGdCy9Y4wxjo$647e889e5e6a5d50031b6096ce7197752cbea39aa9cb0c12c5bf120c9f95b215c17245ac348d1532000b8723e5a8a1b62ef8f47c0ddc55c0e0db7d23a3fe15e4', 'ramp_agent', 0, 'Emma', 'Sheehan', 5),
    (27, 'ORK', 517330313, 'scrypt:32768:8:1$wdlwUwclxwNKccoQ$5e0ad210e35cf772b16f1bf6018d69b382da8d438c09231d70edddb09a68db60e311b0ba3a07f0602b38fb0a2671d73ef979efe22f0a98121ecc6ee39fa06fbd', 'ramp_agent', 0, 'Cian', 'Buckley', 6),
    (28, 'ORK', 517330314, 'scrypt:32768:8:1$F1gMB9rIwcqzgnxf$91b7aafffed69e4b7d8beed13a8cff0b8da6408dc6b824cb6872003400856ee6941e1f453075816938d1f42d58e56265fe12f3fc7b0ade11e2222bbf07cdfb4b', 'ramp_agent', 0, 'Lucy', 'Harte', 6);
INSERT INTO userSkills (userID, skill) VALUES
    (3, 'Tug'),
    (3, 'Steps'),
    (3, 'Baggage'),
    (4, 'Belt loader'),
    (4, 'Baggage'),
    (5, 'Tug'),
    (5, 'Belt loader'),
    (6, 'Steps'),
    (6, 'Baggage'),
    (7, 'Tug'),
    (8, 'Baggage'),
    (8, 'Steps'),
    (9, 'Belt loader'),
    (10, 'Tug'),
    (10, 'Baggage'),
    (11, 'Steps'),
    (12, 'Belt loader'),
    (12, 'Baggage'),
    (13, 'Tug'),
    (14, 'Baggage'),
    (15, 'Steps'),
    (15, 'Belt loader'),
    (16, 'Tug'),
    (16, 'Steps'),
    (17, 'Baggage'),
    (18, 'Belt loader'),
    (19, 'Tug'),
    (19, 'Baggage'),
    (20, 'Steps'),
    (21, 'Belt loader'),
    (23, 'Tug'),
    (23, 'Steps'),
    (23, 'Baggage'),
    (24, 'Belt loader'),
    (24, 'Baggage'),
    (25, 'Tug'),
    (26, 'Baggage'),
    (27, 'Steps'),
    (28, 'Belt loader'),
    (28, 'Tug');
INSERT INTO shifts (id, airportCode, teamID, shiftDate, startTime, endTime) VALUES
    (1, 'DUB', 1, date('now'), strftime('%Y-%m-%dT05:00:00Z','now'), strftime('%Y-%m-%dT13:00:00Z','now')),
    (2, 'DUB', 2, date('now'), strftime('%Y-%m-%dT13:00:00Z','now'), strftime('%Y-%m-%dT21:00:00Z','now')),
    (3, 'DUB', 3, date('now'), strftime('%Y-%m-%dT07:00:00Z','now'), strftime('%Y-%m-%dT15:00:00Z','now')),
    (4, 'DUB', 4, date('now'), strftime('%Y-%m-%dT15:00:00Z','now'), strftime('%Y-%m-%dT23:00:00Z','now')),
    (5, 'ORK', 5, date('now'), strftime('%Y-%m-%dT06:00:00Z','now'), strftime('%Y-%m-%dT14:00:00Z','now')),
    (6, 'ORK', 6, date('now'), strftime('%Y-%m-%dT14:00:00Z','now'), strftime('%Y-%m-%dT22:00:00Z','now'));
INSERT INTO shiftAssignments (id, shiftID, userID, coveringSkill, status, expectedArrival) VALUES
    (1, 1, 3, NULL, 'ready', NULL),
    (2, 2, 4, NULL, 'ready', NULL),
    (3, 3, 5, NULL, 'ready', NULL),
    (4, 4, 6, NULL, 'ready', NULL),
    (5, 1, 7, 'Belt loader', 'ready', NULL),
    (6, 1, 8, NULL, 'sick', NULL),
    (7, 1, 9, NULL, 'ready', NULL),
    (8, 2, 10, NULL, 'ready', NULL),
    (9, 2, 11, NULL, 'ready', NULL),
    (10, 2, 12, NULL, 'delayed', strftime('%Y-%m-%dT%H:%M:%SZ','now','+30 minutes')),
    (11, 3, 13, NULL, 'ready', NULL),
    (12, 3, 14, NULL, 'sick', NULL),
    (13, 3, 15, 'Baggage', 'ready', NULL),
    (14, 4, 16, NULL, 'ready', NULL),
    (15, 4, 17, NULL, 'delayed', strftime('%Y-%m-%dT%H:%M:%SZ','now','+45 minutes')),
    (16, 4, 18, NULL, 'ready', NULL),
    (17, 5, 23, NULL, 'ready', NULL),
    (18, 6, 24, NULL, 'ready', NULL),
    (19, 5, 25, NULL, 'ready', NULL),
    (20, 5, 26, NULL, 'ready', NULL),
    (21, 6, 27, NULL, 'sick', NULL),
    (22, 6, 28, NULL, 'delayed', strftime('%Y-%m-%dT%H:%M:%SZ','now','+20 minutes'));
INSERT INTO flights (airportCode, teamID, flightNumber, airline, origin, scheduledArrival, scheduledDeparture, stand, status) VALUES
    ('DUB', 1, 'EI 105', 'Aer Lingus', 'LHR', strftime('%Y-%m-%dT05:30:00Z','now'), strftime('%Y-%m-%dT06:20:00Z','now'), '12', 'departed'),
    ('DUB', 1, 'FR 1812', 'Ryanair', 'STN', strftime('%Y-%m-%dT06:10:00Z','now'), strftime('%Y-%m-%dT07:00:00Z','now'), '4', 'departed'),
    ('DUB', 3, 'BA 832', 'British Airways', 'LHR', strftime('%Y-%m-%dT07:05:00Z','now'), strftime('%Y-%m-%dT08:00:00Z','now'), '21', 'on_time'),
    ('DUB', 3, 'LH 978', 'Lufthansa', 'FRA', strftime('%Y-%m-%dT08:15:00Z','now'), strftime('%Y-%m-%dT09:10:00Z','now'), '18', 'on_time'),
    ('DUB', 1, 'EI 3', 'Aer Lingus', 'JFK', strftime('%Y-%m-%dT08:40:00Z','now'), strftime('%Y-%m-%dT10:10:00Z','now'), '7', 'on_time'),
    ('DUB', 3, 'KL 1085', 'KLM', 'AMS', strftime('%Y-%m-%dT09:30:00Z','now'), strftime('%Y-%m-%dT10:25:00Z','now'), '15', 'on_time'),
    ('DUB', 1, 'FR 224', 'Ryanair', 'BCN', strftime('%Y-%m-%dT10:45:00Z','now'), strftime('%Y-%m-%dT11:35:00Z','now'), '5', 'on_time'),
    ('DUB', 1, 'AF 1250', 'Air France', 'CDG', strftime('%Y-%m-%dT11:20:00Z','now'), strftime('%Y-%m-%dT12:15:00Z','now'), '19', 'on_time'),
    ('DUB', 3, 'VY 8765', 'Vueling', 'MAD', strftime('%Y-%m-%dT12:30:00Z','now'), strftime('%Y-%m-%dT13:25:00Z','now'), '6', 'on_time'),
    ('DUB', 2, 'EK 162', 'Emirates', 'DXB', strftime('%Y-%m-%dT13:10:00Z','now'), strftime('%Y-%m-%dT14:40:00Z','now'), '31', 'on_time'),
    ('DUB', 2, 'EI 154', 'Aer Lingus', 'MAN', strftime('%Y-%m-%dT13:45:00Z','now'), strftime('%Y-%m-%dT14:35:00Z','now'), '11', 'delayed'),
    ('DUB', 2, 'DL 41', 'Delta', 'JFK', strftime('%Y-%m-%dT14:20:00Z','now'), strftime('%Y-%m-%dT15:50:00Z','now'), '29', 'on_time'),
    ('DUB', 2, 'FR 6112', 'Ryanair', 'LIS', strftime('%Y-%m-%dT15:05:00Z','now'), strftime('%Y-%m-%dT15:55:00Z','now'), '3', 'on_time'),
    ('DUB', 4, 'UA 117', 'United', 'EWR', strftime('%Y-%m-%dT15:40:00Z','now'), strftime('%Y-%m-%dT17:10:00Z','now'), '28', 'on_time'),
    ('DUB', 4, 'BA 838', 'British Airways', 'LHR', strftime('%Y-%m-%dT16:15:00Z','now'), strftime('%Y-%m-%dT17:10:00Z','now'), '22', 'delayed'),
    ('DUB', NULL, 'EI 623', 'Aer Lingus', 'EDI', strftime('%Y-%m-%dT17:00:00Z','now'), strftime('%Y-%m-%dT17:50:00Z','now'), NULL, 'on_time'),
    ('DUB', 4, 'LH 980', 'Lufthansa', 'FRA', strftime('%Y-%m-%dT18:20:00Z','now'), strftime('%Y-%m-%dT19:15:00Z','now'), '17', 'on_time'),
    ('DUB', 4, 'KL 1087', 'KLM', 'AMS', strftime('%Y-%m-%dT19:05:00Z','now'), strftime('%Y-%m-%dT20:00:00Z','now'), '14', 'on_time'),
    ('DUB', NULL, 'FR 9034', 'Ryanair', 'STN', strftime('%Y-%m-%dT20:30:00Z','now'), strftime('%Y-%m-%dT21:20:00Z','now'), NULL, 'on_time'),
    ('DUB', 4, 'EI 157', 'Aer Lingus', 'MAN', strftime('%Y-%m-%dT21:40:00Z','now'), strftime('%Y-%m-%dT22:30:00Z','now'), '10', 'cancelled'),
    ('ORK', 5, 'EI 501', 'Aer Lingus', 'LHR', strftime('%Y-%m-%dT06:45:00Z','now'), strftime('%Y-%m-%dT07:35:00Z','now'), '2', 'on_time'),
    ('ORK', 5, 'FR 3320', 'Ryanair', 'STN', strftime('%Y-%m-%dT09:20:00Z','now'), strftime('%Y-%m-%dT10:10:00Z','now'), '4', 'on_time'),
    ('ORK', 5, 'KL 1093', 'KLM', 'AMS', strftime('%Y-%m-%dT11:50:00Z','now'), strftime('%Y-%m-%dT12:40:00Z','now'), '1', 'on_time'),
    ('ORK', 6, 'EI 513', 'Aer Lingus', 'LHR', strftime('%Y-%m-%dT14:30:00Z','now'), strftime('%Y-%m-%dT15:20:00Z','now'), '3', 'delayed'),
    ('ORK', 6, 'FR 5710', 'Ryanair', 'BCN', strftime('%Y-%m-%dT17:15:00Z','now'), strftime('%Y-%m-%dT18:05:00Z','now'), '5', 'on_time'),
    ('ORK', NULL, 'EI 519', 'Aer Lingus', 'MAN', strftime('%Y-%m-%dT19:40:00Z','now'), strftime('%Y-%m-%dT20:30:00Z','now'), NULL, 'on_time');
-- Flights that are already under way or finished were approved earlier in the day.
-- The rest stay pending so there is something for the supervisor to approve.
UPDATE flights SET approved = 1 WHERE teamID IS NOT NULL AND status IN ('departed', 'arrived', 'delayed');
UPDATE flights SET approved = 1 WHERE flightNumber IN ('BA 832', 'EK 162', 'UA 117', 'EI 501');

INSERT INTO absenceReports (id, shiftAssignmentID, reportedAt) VALUES
    (1, 6, strftime('%Y-%m-%dT%H:%M:%SZ','now','-90 minutes')),
    (2, 12, strftime('%Y-%m-%dT%H:%M:%SZ','now','-80 minutes')),
    (3, 21, strftime('%Y-%m-%dT%H:%M:%SZ','now','-70 minutes'));
INSERT INTO reassignmentRequests (id, absenceReportID, proposedUserID, status, decidedBy, decidedAt) VALUES
    (1, 1, 20, 'pending', NULL, NULL),
    (2, 2, 19, 'rejected', 2, strftime('%Y-%m-%dT%H:%M:%SZ','now','-30 minutes'));
INSERT INTO notifications (userID, message, isRead) VALUES
    (2, 'Reassignment request pending: Darragh Ryan (Team 1) called in sick.', 0),
    (3, 'Darragh Ryan has called in sick for today''s shift.', 0),
    (5, 'Reassignment request for Sean Maguire was rejected by Declan Murphy.', 1);
