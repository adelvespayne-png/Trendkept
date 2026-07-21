---
name: sql-queries
description: Write SQL queries to pull, filter, join, or aggregate records from a described database schema. Use whenever the user describes tables/columns and wants a query written, or pastes a schema and asks a data question.
---

# Sql Queries

## Workflow
1. Get the schema (table names, columns, relationships) - ask if not provided, don't guess column names.
2. Write the query using standard SQL, calling out any dialect-specific syntax (Postgres vs MySQL vs SQL Server) if the user specifies an engine.
3. For complex joins/aggregations, briefly explain the logic (why this join, why this grouping) so the user can verify it's pulling what they actually want.
4. If the user can execute code, offer to run it against sample data (via bash/Python + sqlite) to sanity-check the query rather than just asserting it's correct.
