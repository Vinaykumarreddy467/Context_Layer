-- git_branch is optional in the API contract: core.create_handoff and the
-- MCP tool both default it to None. The original schema required a string,
-- which rejected handoffs created without a branch. Redefine as optional.
REMOVE FIELD git_branch ON handoff;
DEFINE FIELD git_branch ON handoff TYPE option<string>;