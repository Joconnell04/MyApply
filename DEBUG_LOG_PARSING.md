# Debug Log Parsing System

## Overview

This system is designed with the **assumption that API responses will ALWAYS be malformed or unreliable**. Instead of relying on the workflow's direct output, we prioritize parsing data from debug logs, which contain the complete execution trace.

## Architecture

### Core Principle
**Debug logs are the source of truth, not API responses.**

### Workflow

```
1. Workflow Executes
   ↓
2. Debug logs are written (during execution)
   ↓
3. API response returns (possibly malformed)
   ↓
4. PRIMARY: Parse from debug logs
   ↓
5. FALLBACK: Try parsing API response
   ↓
6. LAST RESORT: Use old decoder
   ↓
7. If all fail → Status: "failed"
   If any succeed → Status: "succeeded"
```

## Components

### 1. Debug Log Parser Service
**File**: `services/debug_log_parser.py`

**Main Function**: `parse_complete_workflow_from_debug_logs(session, application_id)`

**Returns**:
```python
{
    "structured_job": {...} or None,
    "resume_bullets": [...] or None,
    "cover_letter": str or None,
    "run_id": str or None,
    "parsing_strategy": str,  # e.g., "debug_log_deep_search"
    "success": bool
}
```

**Parsing Strategies**:
1. **Direct extraction**: Look for data in `response_data`
2. **Nested search**: Recursively search all dict/list structures
3. **Markdown unwrapping**: Extract JSON from ````json` code blocks
4. **Line reconstruction**: Rebuild JSON from line-by-line arrays
5. **Text parsing**: Extract from plain text strings

### 2. JD Ingest Integration
**File**: `routers/jd_ingest.py`

**Flow**:
```python
# After workflow completes
time.sleep(0.5)  # Give debug log time to be written

# PRIMARY: Parse from debug logs
debug_result = parse_complete_workflow_from_debug_logs(session, app_id)

if debug_result["success"]:
    # Use debug log data
    structured_job = debug_result["structured_job"]
    resume_bullets = debug_result["resume_bullets"]
    # ... mark as succeeded
else:
    # FALLBACK: Try API response
    # LAST RESORT: Try old decoder
```

### 3. Manual Reparse Endpoint
**Endpoint**: `POST /api/applications/{application_id}/reparse`

**Purpose**: Allow users to manually trigger reparsing from debug logs

**Use Cases**:
- Initial parsing failed
- Debug logs weren't ready yet (race condition)
- User wants to force re-extraction

**Response**:
```json
{
    "ok": true,
    "message": "Application reparsed successfully from debug logs.",
    "jd_status": "succeeded",
    "resume_status": "succeeded",
    "has_structured_job": true,
    "has_resume_bullets": true,
    "parsing_strategy": "debug_log_deep_search"
}
```

### 4. UI Integration
**File**: `templates/application_detail.html`

**Button**: "Reparse from Debug Logs"
- Visible when `resume_status != "succeeded"`
- Calls `/api/applications/{id}/reparse`
- Shows success/failure message
- Refreshes page on success

## Handling Edge Cases

### Case 1: Markdown-Wrapped JSON
**Input**:
```json
{
    "resume_bullet_points": [
        "```json",
        "{",
        "  \"reasoning\": \"...\",",
        "  \"plan\": [...],",
        "  \"resume_bullet_points\": [...]",
        "}",
        "```"
    ]
}
```

**Solution**: `_reconstruct_json_from_lines()` joins and parses

### Case 2: Deeply Nested Output
**Input**:
```json
{
    "output": {
        "result": {
            "data": {
                "resume_bullet_points": [...]
            }
        }
    }
}
```

**Solution**: `_extract_from_nested_structure()` recursively searches

### Case 3: Plain Text Response
**Input**:
```
"- Engineered scalable APIs\n- Collaborated with teams\n..."
```

**Solution**: `_extract_bullet_list()` parses line-by-line

### Case 4: No Data Found
**Result**:
- `success: false`
- Status remains "failed"
- User can manually reparse later

## Status Values

| Status | Meaning |
|--------|---------|
| `pending` | Workflow not started |
| `running` | Workflow currently executing |
| `succeeded` | Data successfully extracted (from debug logs or API) |
| `failed` | No valid data found anywhere |
| `aborted` | User manually stopped the run |

## Metadata Fields

Added to `resume_output`:
- `decoder_source`: `"debug_log_parser"` (new) or `"agentkit_debug_log"` (old)
- `parsing_strategy`: e.g., `"debug_log_deep_search"`

## Best Practices

### For Developers

1. **Always assume API responses are unreliable**
   - Don't trust the direct output
   - Always check debug logs first

2. **Add delays when needed**
   - Debug logs are written asynchronously
   - A 0.5s delay ensures they're available

3. **Log everything**
   - Debug logs should contain complete workflow output
   - Include all intermediate steps

4. **Test with malformed data**
   - Create tests with markdown-wrapped JSON
   - Create tests with nested structures
   - Create tests with missing fields

### For Users

1. **Check debug logs if output is empty**
   - Click "Load Debug Logs" on detail page
   - Look for the response_data section

2. **Use "Reparse from Debug Logs" button**
   - If resume bullets don't appear
   - If status stuck at "failed" but logs show data
   - If you want to retry parsing

3. **Wait a moment after submission**
   - Debug logs take a moment to be written
   - If you see "no output", wait 5 seconds and reparse

## Testing

All tests pass:
```bash
python -m pytest tests/test_workflows.py -v
# test_resume_builder_v2_ingest_and_resume PASSED
# test_jd_ingest_uses_debug_decoder_when_workflow_reports_failure PASSED
```

Tests verify:
- Debug log parsing works
- Markdown-wrapped JSON is handled
- Status is set to "succeeded" when data found
- Correct decoder_source is set

## Troubleshooting

### Problem: "No output" shown but debug logs have data

**Solution**: Click "Reparse from Debug Logs" button

### Problem: Status stuck at "running"

**Solution**:
1. Check if workflow actually completed (debug logs show completion)
2. Abort the run if stuck
3. Reparse from debug logs

### Problem: Bullets shown but not formatted correctly

**Solution**:
1. Check `resume_output.resume_bullets` in debug logs
2. Verify parsing extracted all bullets
3. May need to update `_extract_bullet_list()` logic

### Problem: Structured job data missing

**Solution**:
1. Check debug logs for `structured_job_data` or `job_scraper_result`
2. Verify keys match expected format (company, role, locations, etc.)
3. May need to add more fallback keys to parser

## Future Improvements

1. **Async Background Parser**
   - Run parser in background task
   - Poll until data is available
   - Automatically update status when found

2. **Auto-Retry Logic**
   - If parsing fails, retry after 1s, 2s, 5s delays
   - Up to 3 attempts
   - Only mark as "failed" after all retries exhausted

3. **Better Error Messages**
   - Show which parsing strategy was attempted
   - Show what data was found but rejected
   - Link directly to debug logs

4. **Frontend Real-Time Updates**
   - WebSocket connection for status updates
   - Show "Parsing..." indicator
   - Auto-refresh when parsing completes

## Related Files

- `services/debug_log_parser.py` - Core parsing logic
- `routers/jd_ingest.py` - Primary workflow endpoint
- `routers/resume_build.py` - Resume build endpoint
- `app.py` - Reparse API endpoint
- `templates/application_detail.html` - UI with reparse button
- `tests/test_workflows.py` - Test coverage
- `services/workflow_output_parser.py` - Old parser (fallback)
- `debug_logger.py` - Debug log writing logic
