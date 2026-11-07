-- Real airports: IATA code, airport name and IANA timezone.
-- Run after schema.sql:   sqlite3 app.db < insert_airports.sql
-- This is a starter list. Add any other airport with the same INSERT INTO pattern.

-- Ireland
INSERT INTO airports (airportCode, name, timezone) VALUES
    ('DUB', 'Dublin Airport', 'Europe/Dublin'),
    ('ORK', 'Cork Airport', 'Europe/Dublin'),
    ('SNN', 'Shannon Airport', 'Europe/Dublin'),
    ('NOC', 'Ireland West Airport Knock', 'Europe/Dublin');

-- United Kingdom
INSERT INTO airports (airportCode, name, timezone) VALUES
    ('LHR', 'London Heathrow Airport', 'Europe/London'),
    ('LGW', 'London Gatwick Airport', 'Europe/London'),
    ('MAN', 'Manchester Airport', 'Europe/London'),
    ('EDI', 'Edinburgh Airport', 'Europe/London');

-- Europe
INSERT INTO airports (airportCode, name, timezone) VALUES
    ('AMS', 'Amsterdam Airport Schiphol', 'Europe/Amsterdam'),
    ('CDG', 'Paris Charles de Gaulle Airport', 'Europe/Paris'),
    ('FRA', 'Frankfurt Airport', 'Europe/Berlin'),
    ('MUC', 'Munich Airport', 'Europe/Berlin'),
    ('MAD', 'Madrid-Barajas Airport', 'Europe/Madrid'),
    ('BCN', 'Barcelona-El Prat Airport', 'Europe/Madrid'),
    ('FCO', 'Rome Fiumicino Airport', 'Europe/Rome'),
    ('ZRH', 'Zurich Airport', 'Europe/Zurich'),
    ('CPH', 'Copenhagen Airport', 'Europe/Copenhagen'),
    ('LIS', 'Lisbon Humberto Delgado Airport', 'Europe/Lisbon'),
    ('IST', 'Istanbul Airport', 'Europe/Istanbul');

-- North America
INSERT INTO airports (airportCode, name, timezone) VALUES
    ('JFK', 'John F. Kennedy International Airport', 'America/New_York'),
    ('EWR', 'Newark Liberty International Airport', 'America/New_York'),
    ('BOS', 'Boston Logan International Airport', 'America/New_York'),
    ('MIA', 'Miami International Airport', 'America/New_York'),
    ('ATL', 'Hartsfield-Jackson Atlanta International Airport', 'America/New_York'),
    ('ORD', 'Chicago O''Hare International Airport', 'America/Chicago'),
    ('DFW', 'Dallas/Fort Worth International Airport', 'America/Chicago'),
    ('DEN', 'Denver International Airport', 'America/Denver'),
    ('LAX', 'Los Angeles International Airport', 'America/Los_Angeles'),
    ('SFO', 'San Francisco International Airport', 'America/Los_Angeles'),
    ('SEA', 'Seattle-Tacoma International Airport', 'America/Los_Angeles'),
    ('YYZ', 'Toronto Pearson International Airport', 'America/Toronto'),
    ('YVR', 'Vancouver International Airport', 'America/Vancouver'),
    ('MEX', 'Mexico City International Airport', 'America/Mexico_City');

-- South America
INSERT INTO airports (airportCode, name, timezone) VALUES
    ('GRU', 'Sao Paulo-Guarulhos International Airport', 'America/Sao_Paulo');

-- Middle East
INSERT INTO airports (airportCode, name, timezone) VALUES
    ('DXB', 'Dubai International Airport', 'Asia/Dubai'),
    ('AUH', 'Abu Dhabi International Airport', 'Asia/Dubai'),
    ('DOH', 'Hamad International Airport', 'Asia/Qatar');

-- Asia
INSERT INTO airports (airportCode, name, timezone) VALUES
    ('SIN', 'Singapore Changi Airport', 'Asia/Singapore'),
    ('HKG', 'Hong Kong International Airport', 'Asia/Hong_Kong'),
    ('HND', 'Tokyo Haneda Airport', 'Asia/Tokyo'),
    ('NRT', 'Narita International Airport', 'Asia/Tokyo'),
    ('ICN', 'Incheon International Airport', 'Asia/Seoul'),
    ('PEK', 'Beijing Capital International Airport', 'Asia/Shanghai'),
    ('PVG', 'Shanghai Pudong International Airport', 'Asia/Shanghai'),
    ('BKK', 'Bangkok Suvarnabhumi Airport', 'Asia/Bangkok'),
    ('DEL', 'Delhi Indira Gandhi International Airport', 'Asia/Kolkata'),
    ('BOM', 'Mumbai Chhatrapati Shivaji Maharaj International Airport', 'Asia/Kolkata');

-- Oceania
INSERT INTO airports (airportCode, name, timezone) VALUES
    ('SYD', 'Sydney Kingsford Smith Airport', 'Australia/Sydney'),
    ('MEL', 'Melbourne Airport', 'Australia/Melbourne'),
    ('AKL', 'Auckland Airport', 'Pacific/Auckland');

-- Africa
INSERT INTO airports (airportCode, name, timezone) VALUES
    ('JNB', 'Johannesburg O. R. Tambo International Airport', 'Africa/Johannesburg'),
    ('CPT', 'Cape Town International Airport', 'Africa/Johannesburg'),
    ('CAI', 'Cairo International Airport', 'Africa/Cairo'),
    ('ADD', 'Addis Ababa Bole International Airport', 'Africa/Addis_Ababa'),
    ('NBO', 'Nairobi Jomo Kenyatta International Airport', 'Africa/Nairobi'),
    ('LOS', 'Lagos Murtala Muhammed International Airport', 'Africa/Lagos');