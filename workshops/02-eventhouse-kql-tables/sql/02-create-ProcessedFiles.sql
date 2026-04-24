-- Workshop 02 — Create ProcessedFiles audit/control table
-- Target: Fabric Warehouse "wh_control_framework"
-- Run in the Warehouse SQL query editor

IF OBJECT_ID('dbo.ProcessedFiles', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.ProcessedFiles (
        FileName      VARCHAR(260)  NOT NULL,
        IngestedAtUtc DATETIME2(3)  NOT NULL,
        RowCount_     BIGINT        NOT NULL,   -- trailing underscore: ROWCOUNT is reserved in T-SQL
        Status        VARCHAR(32)   NOT NULL,   -- Success | Failed | Skipped-Duplicate
        PipelineName  VARCHAR(200)  NULL,
        PipelineRunId VARCHAR(64)   NULL,
        RunAsUser     VARCHAR(200)  NULL,
        ErrorMsg      VARCHAR(4000) NULL
    );
END;
GO

-- Helpful read patterns
-- SELECT Status, COUNT(*) AS Files, SUM(RowCount_) AS Rows
-- FROM dbo.ProcessedFiles
-- GROUP BY Status;
