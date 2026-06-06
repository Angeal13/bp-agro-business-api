-- ============================================================
-- BP Agro — Unified Aurora Schema
-- Target : AWS Aurora MySQL 8.0
-- Encoding: utf8mb4
--
-- This is the single source of truth for all BP Agro tables:
--   • Core platform  (client, farms, zones, sensors, gateway,
--                     soildata, sync_log, global_sync_queue)
--   • Alert system   (optimal_conditions)
--   • Botanist Dashboard (botanist_interventions,
--                         botanist_planting_dates)
--   • Rain Integration (rain_events, weather_poll_log,
--                       alert_suppression_log)
--
-- Run order:
--   1. This file   →  creates all tables
--   2. seed_optimal_conditions.sql  →  fills crop thresholds
--
-- After running, set farm coordinates for weather API:
--   UPDATE farms
--   SET latitude=-1.2921, longitude=36.8219, timezone='Africa/Nairobi'
--   WHERE farm_id='F001';
-- ============================================================

SET NAMES utf8mb4;
SET time_zone = '+00:00';


-- ─────────────────────────────────────────────────────────────
-- 1. CLIENTS
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS client (
    client_id   VARCHAR(10)  PRIMARY KEY,
    client_name VARCHAR(100) NOT NULL,
    email       VARCHAR(255),
    whatsapp    VARCHAR(50),
    created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_client_name (client_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ─────────────────────────────────────────────────────────────
-- 2. FARMS
--    latitude / longitude / timezone added for Rain Integration
--    (Open-Meteo weather API calls — set once manually per farm)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS farms (
    farm_id     VARCHAR(10)   PRIMARY KEY,
    client_id   VARCHAR(10)   NOT NULL,
    farm_name   VARCHAR(100)  NOT NULL,
    emails      TEXT,
    whatsapps   TEXT,
    farm_length DECIMAL(10,2) DEFAULT 0,
    farm_width  DECIMAL(10,2) DEFAULT 0,
    -- Rain Integration: weather API coordinates (set manually)
    latitude    DECIMAL(10,6) NULL    COMMENT 'Farm GPS latitude  — required for weather API',
    longitude   DECIMAL(10,6) NULL    COMMENT 'Farm GPS longitude — required for weather API',
    timezone    VARCHAR(50)   DEFAULT 'UTC' COMMENT 'IANA timezone, e.g. Africa/Malabo',
    created_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES client(client_id),
    INDEX idx_farm_name (farm_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ─────────────────────────────────────────────────────────────
-- 3. ZONES
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS zones (
    zone_id    INT          AUTO_INCREMENT PRIMARY KEY,
    farm_id    VARCHAR(10)  NOT NULL,
    zone_code  VARCHAR(10)  NOT NULL,
    crop       VARCHAR(50)  DEFAULT '?',
    x_axis     VARCHAR(10),             -- grid column (0-based)
    y_axis     VARCHAR(10),             -- grid row    (0-based)
    created_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_farm_zone (farm_id, zone_code),
    FOREIGN KEY (farm_id) REFERENCES farms(farm_id) ON DELETE CASCADE,
    INDEX idx_zone_code (zone_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ─────────────────────────────────────────────────────────────
-- 4. SENSORS
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sensors (
    machine_id   VARCHAR(50)  PRIMARY KEY,
    farm_id      VARCHAR(10)  NULL,
    zone_code    VARCHAR(10)  NULL,
    installation DATE         NULL,
    is_active    BOOLEAN      DEFAULT 0,
    crop         VARCHAR(50)  NULL,
    created_at   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_seen    TIMESTAMP    NULL,
    FOREIGN KEY (farm_id) REFERENCES farms(farm_id) ON DELETE SET NULL,
    INDEX idx_farm_id   (farm_id),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ─────────────────────────────────────────────────────────────
-- 5. GATEWAY REGISTRY
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gateway (
    gateway_id       VARCHAR(50)  PRIMARY KEY,
    farm_id          VARCHAR(10)  NULL,
    local_ip         VARCHAR(15),
    public_ip        VARCHAR(15),
    all_ips          TEXT,
    hostname         VARCHAR(100),
    mac_address      VARCHAR(17),
    setup_date       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    last_heartbeat   TIMESTAMP    NULL,
    heartbeat_count  INT          DEFAULT 0,
    status           ENUM('online','offline','maintenance') DEFAULT 'offline',
    firmware_version VARCHAR(20),
    pi_model         VARCHAR(50),
    location_notes   TEXT,
    last_ip_change   TIMESTAMP    NULL,
    total_ip_changes INT          DEFAULT 0,
    FOREIGN KEY (farm_id) REFERENCES farms(farm_id),
    INDEX idx_farm   (farm_id),
    INDEX idx_status (status),
    INDEX idx_local_ip (local_ip)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ─────────────────────────────────────────────────────────────
-- 6. SOIL DATA
--    rain_* columns added for Rain Integration — all nullable,
--    safe default values so existing rows are unaffected.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS soildata (
    id          BIGINT        AUTO_INCREMENT PRIMARY KEY,
    machine_id  VARCHAR(50)   NOT NULL,
    timestamp   TIMESTAMP     NOT NULL,
    moisture    DECIMAL(5,2),
    temperature DECIMAL(5,2),
    ec          DECIMAL(5,2),
    ph          DECIMAL(3,2),
    n           DECIMAL(5,2),
    p           DECIMAL(5,2),
    k           DECIMAL(5,2),
    farm_id     VARCHAR(10)   NULL,
    zone_code   VARCHAR(10)   NULL,
    batch_id    VARCHAR(50)   NULL,
    -- Rain Integration flags
    rain_tier              TINYINT      NULL    COMMENT '0=clear,1=drizzle,2=moderate,3=heavy',
    rain_event_id          BIGINT       NULL    COMMENT 'FK to rain_events (set after that table exists)',
    post_rain_recovery     BOOLEAN      DEFAULT FALSE COMMENT 'TRUE during 2h recovery window after rain',
    precip_mmh_at_reading  DECIMAL(5,2) NULL    COMMENT 'Precipitation rate mm/h at time of reading',
    created_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (machine_id) REFERENCES sensors(machine_id),
    INDEX idx_machine_timestamp (machine_id, timestamp),
    INDEX idx_farm_timestamp    (farm_id, timestamp),
    INDEX idx_zone_timestamp    (zone_code, timestamp),
    INDEX idx_rain_tier         (farm_id, rain_tier, timestamp),
    INDEX idx_rain_event        (rain_event_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ─────────────────────────────────────────────────────────────
-- 7. OPTIMAL CONDITIONS
--    Crop thresholds for the alert system and botanist dashboard.
--    Populated by seed_optimal_conditions.sql after this script.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS optimal_conditions (
    crop                  VARCHAR(50)   NOT NULL PRIMARY KEY,
    temperature_min       DECIMAL(4,2)  NOT NULL,
    temperature_max       DECIMAL(4,2)  NOT NULL,
    temperature_optimal   DECIMAL(4,2)  NOT NULL,
    soil_moisture_min     DECIMAL(4,2)  NOT NULL,
    soil_moisture_max     DECIMAL(4,2)  NOT NULL,
    soil_moisture_optimal DECIMAL(4,2)  NOT NULL,
    ph_min                DECIMAL(3,2)  NOT NULL,
    ph_max                DECIMAL(3,2)  NOT NULL,
    ph_optimal            DECIMAL(3,2)  NOT NULL,
    ec_min                DECIMAL(3,2)  NOT NULL,
    ec_max                DECIMAL(3,2)  NOT NULL,
    ec_optimal            DECIMAL(3,2)  NOT NULL,
    nitrogen_min          DECIMAL(6,2)  NOT NULL,
    nitrogen_max          DECIMAL(6,2)  NOT NULL,
    nitrogen_optimal      DECIMAL(6,2)  NOT NULL,
    phosphorus_min        DECIMAL(6,2)  NOT NULL,
    phosphorus_max        DECIMAL(6,2)  NOT NULL,
    phosphorus_optimal    DECIMAL(6,2)  NOT NULL,
    potassium_min         DECIMAL(6,2)  NOT NULL,
    potassium_max         DECIMAL(6,2)  NOT NULL,
    potassium_optimal     DECIMAL(6,2)  NOT NULL,
    -- Agronomic metadata
    companion_crops       TEXT          DEFAULT NULL,
    antagonist_crops      TEXT          DEFAULT NULL,
    companion_notes       TEXT          DEFAULT NULL,
    growth_habit          ENUM('bush','vine','climbing','ground_cover','tree','root','leafy_green','grass','shrub') DEFAULT NULL,
    root_depth            ENUM('shallow','medium','deep') DEFAULT NULL,
    maturity_days         INT           DEFAULT NULL,
    season                ENUM('cool','warm','tropical','all_season') DEFAULT NULL,
    pest_repellent        TINYINT(1)    DEFAULT 0,
    attracts_beneficials  TINYINT(1)    DEFAULT 0,
    nitrogen_fixer        TINYINT(1)    DEFAULT 0,
    allelopathic          TINYINT(1)    DEFAULT 0,
    created_at            TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY crop_name (crop)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ─────────────────────────────────────────────────────────────
-- 8. SYNC LOG
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sync_log (
    log_id        BIGINT      AUTO_INCREMENT PRIMARY KEY,
    farm_id       VARCHAR(10) NOT NULL,
    batch_id      VARCHAR(50) NOT NULL,
    record_count  INT         NOT NULL,
    start_time    TIMESTAMP   NOT NULL,
    end_time      TIMESTAMP   NOT NULL,
    status        ENUM('success','failed','partial') NOT NULL,
    error_message TEXT        NULL,
    created_at    TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_farm_batch (farm_id, batch_id),
    INDEX idx_start_time (start_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ─────────────────────────────────────────────────────────────
-- 9. GLOBAL SYNC QUEUE
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS global_sync_queue (
    sync_id       BIGINT      AUTO_INCREMENT PRIMARY KEY,
    gateway_id    VARCHAR(50) NOT NULL,
    action_type   VARCHAR(50) NOT NULL,
    data          JSON        NOT NULL,
    status        ENUM('pending','processing','completed','failed') DEFAULT 'pending',
    created_at    TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    processed_at  TIMESTAMP   NULL,
    error_message TEXT        NULL,
    INDEX idx_gateway_status (gateway_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ─────────────────────────────────────────────────────────────
-- 10. BOTANIST INTERVENTIONS  (Botanist Dashboard)
--     Field notes, treatment records, and soil sample logs
--     entered by the agronomist via the dashboard.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS botanist_interventions (
    id            BIGINT       AUTO_INCREMENT PRIMARY KEY,
    farm_id       VARCHAR(10)  NOT NULL,
    zone_code     VARCHAR(10)  NOT NULL,
    entry_date    DATE         NOT NULL,
    entry_type    ENUM('intervention','note','sample') NOT NULL DEFAULT 'note',
    title         VARCHAR(255) NOT NULL,
    notes         TEXT,
    -- Comma-separated parameter keys: moisture,ph,nitrogen,...
    params        VARCHAR(255),
    followup_days SMALLINT     NULL,
    outcome       ENUM('improved','unchanged','worsened') NULL,
    created_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (farm_id) REFERENCES farms(farm_id) ON DELETE CASCADE,
    INDEX idx_farm_zone  (farm_id, zone_code),
    INDEX idx_entry_date (entry_date),
    INDEX idx_entry_type (entry_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ─────────────────────────────────────────────────────────────
-- 11. BOTANIST PLANTING DATES  (Botanist Dashboard)
--     Planting dates per zone for growth-stage calculations.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS botanist_planting_dates (
    id            INT          AUTO_INCREMENT PRIMARY KEY,
    farm_id       VARCHAR(10)  NOT NULL,
    zone_code     VARCHAR(10)  NOT NULL,
    planting_date DATE         NOT NULL,
    created_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_farm_zone_planting (farm_id, zone_code),
    FOREIGN KEY (farm_id) REFERENCES farms(farm_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ─────────────────────────────────────────────────────────────
-- 12. RAIN EVENTS  (Rain Integration)
--     One row per precipitation event per farm.
--     Opened when tier transitions from 0 → 1/2/3.
--     Closed when auto-resume confirmation window completes.
--
--     Tier reference:
--       0 : 0 mm/h         Normal operations, all alerts active
--       1 : 0.1–2.5 mm/h   Drizzle — soft degrade, data flagged
--       2 : 2.5–7.5 mm/h   Moderate — reduced freq, agronomic off
--       3 : 7.5+ mm/h      Heavy/storm — full suspension
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rain_events (
    id                 BIGINT        AUTO_INCREMENT PRIMARY KEY,
    farm_id            VARCHAR(10)   NOT NULL,
    started_at         TIMESTAMP     NOT NULL,
    ended_at           TIMESTAMP     NULL,          -- NULL = still active
    tier_peak          TINYINT       NOT NULL,       -- highest tier reached (1/2/3)
    tier_current       TINYINT       NOT NULL,       -- live tier during event
    precip_total_mm    DECIMAL(6,2)  NULL,           -- cumulative from API
    auto_resumed       BOOLEAN       DEFAULT FALSE,
    recovery_end_at    TIMESTAMP     NULL,           -- end of post-rain window
    event_duration_min INT           NULL,           -- filled on close
    FOREIGN KEY (farm_id) REFERENCES farms(farm_id) ON DELETE CASCADE,
    INDEX idx_farm_active  (farm_id, ended_at),
    INDEX idx_farm_started (farm_id, started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Now that rain_events exists, add FK from soildata
ALTER TABLE soildata
    ADD CONSTRAINT fk_soildata_rain_event
    FOREIGN KEY (rain_event_id) REFERENCES rain_events(id) ON DELETE SET NULL;


-- ─────────────────────────────────────────────────────────────
-- 13. WEATHER POLL LOG  (Rain Integration)
--     One row per Open-Meteo API poll per farm (every 10 min).
--     Feeds tier decision logic and provides audit trail.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS weather_poll_log (
    id            BIGINT       AUTO_INCREMENT PRIMARY KEY,
    farm_id       VARCHAR(10)  NOT NULL,
    polled_at     TIMESTAMP    NOT NULL,
    precip_mmh    DECIMAL(5,2) NOT NULL,        -- mm/h from API
    tier_assigned TINYINT      NOT NULL,         -- 0–3
    rain_event_id BIGINT       NULL,             -- FK if tier > 0
    api_source    VARCHAR(50)  DEFAULT 'open-meteo',
    raw_response  JSON         NULL,             -- API snapshot
    FOREIGN KEY (farm_id)       REFERENCES farms(farm_id) ON DELETE CASCADE,
    FOREIGN KEY (rain_event_id) REFERENCES rain_events(id) ON DELETE SET NULL,
    INDEX idx_farm_polled (farm_id, polled_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ─────────────────────────────────────────────────────────────
-- 14. ALERT SUPPRESSION LOG  (Rain Integration)
--     Every alert suppressed during a rain event.
--     Retained for botanist research — what would have fired.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alert_suppression_log (
    id               BIGINT        AUTO_INCREMENT PRIMARY KEY,
    farm_id          VARCHAR(10)   NOT NULL,
    zone_code        VARCHAR(10)   NOT NULL,
    machine_id       VARCHAR(50)   NOT NULL,
    suppressed_at    TIMESTAMP     NOT NULL,
    alert_param      VARCHAR(50)   NOT NULL,    -- e.g. 'ph', 'nitrogen'
    alert_value      DECIMAL(8,2)  NOT NULL,    -- reading that triggered
    alert_threshold  DECIMAL(8,2)  NULL,        -- threshold at the time
    rain_tier        TINYINT       NOT NULL,
    rain_event_id    BIGINT        NOT NULL,
    FOREIGN KEY (farm_id)       REFERENCES farms(farm_id) ON DELETE CASCADE,
    FOREIGN KEY (rain_event_id) REFERENCES rain_events(id) ON DELETE CASCADE,
    INDEX idx_farm_zone  (farm_id, zone_code),
    INDEX idx_event      (rain_event_id),
    INDEX idx_suppressed (suppressed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ─────────────────────────────────────────────────────────────
-- 15. DB USERS
--
--  Two users are used in production:
--
--  a) bpagro_api  — used by Global Management API + Alert System
--                   Full read/write on all operational tables
--
--  b) botanist_api — used by Botanist Dashboard API
--                    Read-only on sensor/soil data,
--                    read/write on botanist_* and rain_* tables
--
--  Uncomment and replace passwords before first deploy.
-- ─────────────────────────────────────────────────────────────

-- === bpagro_api (Global API + Alert System) ===
-- CREATE USER IF NOT EXISTS 'bpagro_api'@'%' IDENTIFIED BY 'CHANGE_ME_BPAGRO';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON soilmonitornig.client              TO 'bpagro_api'@'%';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON soilmonitornig.farms               TO 'bpagro_api'@'%';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON soilmonitornig.zones               TO 'bpagro_api'@'%';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON soilmonitornig.sensors             TO 'bpagro_api'@'%';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON soilmonitornig.gateway             TO 'bpagro_api'@'%';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON soilmonitornig.soildata            TO 'bpagro_api'@'%';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON soilmonitornig.optimal_conditions  TO 'bpagro_api'@'%';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON soilmonitornig.sync_log            TO 'bpagro_api'@'%';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON soilmonitornig.global_sync_queue   TO 'bpagro_api'@'%';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON soilmonitornig.rain_events         TO 'bpagro_api'@'%';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON soilmonitornig.weather_poll_log    TO 'bpagro_api'@'%';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON soilmonitornig.alert_suppression_log TO 'bpagro_api'@'%';

-- === botanist_api (Botanist Dashboard) ===
-- CREATE USER IF NOT EXISTS 'botanist_api'@'%' IDENTIFIED BY 'CHANGE_ME_BOTANIST';
-- GRANT SELECT                          ON soilmonitornig.farms                TO 'botanist_api'@'%';
-- GRANT SELECT                          ON soilmonitornig.zones                TO 'botanist_api'@'%';
-- GRANT SELECT                          ON soilmonitornig.sensors              TO 'botanist_api'@'%';
-- GRANT SELECT                          ON soilmonitornig.soildata             TO 'botanist_api'@'%';
-- GRANT SELECT                          ON soilmonitornig.optimal_conditions   TO 'botanist_api'@'%';
-- GRANT SELECT                          ON soilmonitornig.rain_events          TO 'botanist_api'@'%';
-- GRANT SELECT                          ON soilmonitornig.weather_poll_log     TO 'botanist_api'@'%';
-- GRANT SELECT                          ON soilmonitornig.alert_suppression_log TO 'botanist_api'@'%';
-- GRANT SELECT, INSERT, UPDATE, DELETE  ON soilmonitornig.botanist_interventions  TO 'botanist_api'@'%';
-- GRANT SELECT, INSERT, UPDATE, DELETE  ON soilmonitornig.botanist_planting_dates TO 'botanist_api'@'%';

-- FLUSH PRIVILEGES;
