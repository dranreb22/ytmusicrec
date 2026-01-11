-- ytmusicrec schema (idempotent)
-- NOTE: This file is executed via pyodbc. Do NOT use the 'GO' batch separator.

IF OBJECT_ID('dbo.Videos','U') IS NULL
BEGIN
  CREATE TABLE dbo.Videos (
    video_id NVARCHAR(32) NOT NULL CONSTRAINT PK_Videos PRIMARY KEY,
    query NVARCHAR(200) NULL,
    title NVARCHAR(400) NULL,
    description NVARCHAR(MAX) NULL,
    channel_title NVARCHAR(200) NULL,
    published_at DATETIME2 NULL,
    view_count BIGINT NULL,
    like_count BIGINT NULL,
    comment_count BIGINT NULL,
    fetched_at DATETIME2 NOT NULL
  );
  CREATE INDEX IX_Videos_FetchedAt ON dbo.Videos (fetched_at);
END

IF OBJECT_ID('dbo.Runs','U') IS NULL
BEGIN
  CREATE TABLE dbo.Runs (
    run_id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Runs PRIMARY KEY,
    run_date DATE NOT NULL,
    region_code NVARCHAR(10) NOT NULL,
    query_count INT NOT NULL,
    video_count INT NOT NULL,
    created_at DATETIME2 NOT NULL CONSTRAINT DF_Runs_CreatedAt DEFAULT (SYSUTCDATETIME())
  );
  CREATE INDEX IX_Runs_RunDate ON dbo.Runs (run_date);
END

IF OBJECT_ID('dbo.DailyThemes','U') IS NULL
BEGIN
  CREATE TABLE dbo.DailyThemes (
    run_date DATE NOT NULL,
    theme NVARCHAR(200) NOT NULL,
    score FLOAT NOT NULL,
    examples_json NVARCHAR(MAX) NULL,
    CONSTRAINT PK_DailyThemes PRIMARY KEY (run_date, theme)
  );
  CREATE INDEX IX_DailyThemes_RunDate ON dbo.DailyThemes (run_date);
END

IF OBJECT_ID('dbo.DailyPrompts','U') IS NULL
BEGIN
  CREATE TABLE dbo.DailyPrompts (
    prompt_id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_DailyPrompts PRIMARY KEY,
    run_date DATE NOT NULL,
    tool NVARCHAR(10) NOT NULL,
    prompt NVARCHAR(1000) NOT NULL,
    theme_tags NVARCHAR(400) NULL,
    created_at DATETIME2 NOT NULL CONSTRAINT DF_DailyPrompts_CreatedAt DEFAULT (SYSUTCDATETIME())
  );
  CREATE INDEX IX_DailyPrompts_RunDate ON dbo.DailyPrompts (run_date);
END

-- Ensure one Run per day+region
IF NOT EXISTS (
  SELECT 1 FROM sys.indexes
  WHERE name = 'UX_Runs_RunDate_Region' AND object_id = OBJECT_ID('dbo.Runs')
)
BEGIN
  CREATE UNIQUE INDEX UX_Runs_RunDate_Region ON dbo.Runs (run_date, region_code);
END

-- Prevent duplicate prompts on reruns
IF NOT EXISTS (
  SELECT 1 FROM sys.indexes
  WHERE name = 'UX_DailyPrompts_Unique' AND object_id = OBJECT_ID('dbo.DailyPrompts')
)
BEGIN
  CREATE UNIQUE INDEX UX_DailyPrompts_Unique ON dbo.DailyPrompts (run_date, tool, prompt);
END

IF OBJECT_ID('dbo.QueryCache','U') IS NULL
BEGIN
  CREATE TABLE dbo.QueryCache (
    run_date DATE NOT NULL,
    region_code NVARCHAR(10) NOT NULL,
    query_name NVARCHAR(200) NOT NULL,
    q NVARCHAR(500) NULL,
    video_ids_json NVARCHAR(MAX) NOT NULL,
    fetched_at DATETIME2 NOT NULL,
    CONSTRAINT PK_QueryCache PRIMARY KEY (run_date, region_code, query_name)
  );
END

-- Tracks per-day momentum stats for each theme
IF OBJECT_ID('dbo.DailyThemeTrends', 'U') IS NULL
BEGIN
  CREATE TABLE dbo.DailyThemeTrends (
    run_date DATE NOT NULL,
    theme NVARCHAR(200) NOT NULL,
    score FLOAT NOT NULL,
    prev_score FLOAT NULL,
    delta_1d FLOAT NULL,
    avg_7d FLOAT NULL,
    momentum FLOAT NULL,
    computed_at DATETIME2 NOT NULL CONSTRAINT DF_DailyThemeTrends_computed_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_DailyThemeTrends PRIMARY KEY (run_date, theme)
  );
END

GO

-- Tracks per-query performance so tomorrow can choose better queries
IF OBJECT_ID('dbo.DailyQueryStats', 'U') IS NULL
BEGIN
  CREATE TABLE dbo.DailyQueryStats (
    run_date DATE NOT NULL,
    region_code NVARCHAR(10) NOT NULL,
    query_name NVARCHAR(200) NOT NULL,
    q NVARCHAR(400) NOT NULL,
    video_count INT NOT NULL,
    total_views BIGINT NULL,
    total_likes BIGINT NULL,
    total_comments BIGINT NULL,
    computed_at DATETIME2 NOT NULL CONSTRAINT DF_DailyQueryStats_computed_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_DailyQueryStats PRIMARY KEY (run_date, region_code, query_name)
  );
END
GO

-- Helps prompt evolution: avoid repeats / measure novelty over time
IF OBJECT_ID('dbo.DailyPromptHistory', 'U') IS NULL
BEGIN
  CREATE TABLE dbo.DailyPromptHistory (
    run_date DATE NOT NULL,
    tool NVARCHAR(50) NOT NULL,
    prompt NVARCHAR(1000) NOT NULL,
    prompt_hash VARBINARY(32) NOT NULL, -- SHA2_256
    theme_tags NVARCHAR(400) NULL,
    created_at DATETIME2 NOT NULL CONSTRAINT DF_DailyPromptHistory_created_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_DailyPromptHistory PRIMARY KEY (run_date, tool, prompt_hash)
  );

  CREATE INDEX IX_DailyPromptHistory_ToolDate ON dbo.DailyPromptHistory (tool, run_date);
END
GO
