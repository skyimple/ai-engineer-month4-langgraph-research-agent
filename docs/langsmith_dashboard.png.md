# LangSmith Dashboard Screenshot Placeholder

## Screenshot Location

After running the research agent with LangSmith tracing enabled, a screenshot of the LangSmith dashboard should be saved here.

## How to Capture

1. Run the agent: `python -m src.main "AI"`
2. Go to https://smith.langchain.com/
3. Navigate to your project (research-agent by default)
4. Find the trace from the most recent run
5. Take a screenshot of the trace showing all 4 nodes:
   - planner
   - researcher
   - writer
   - saver

## Expected Trace Structure

The LangSmith trace should show a hierarchy like:
```
- research-agent (project)
  └── [Trace]
      ├── planner_node (first node)
      ├── researcher_node (second node)
      ├── writer_node (third node)
      └── saver_node (fourth node)
```

Each node should show:
- Node name and metadata
- Input/output data
- Execution time
- LLM calls and tool invocations

## Verification

Verify that all 4 nodes appear in the trace with correct metadata:
- `node: "planner"` with `version: "1.0"`
- `node: "researcher"` with `version: "1.0"`
- `node: "writer"` with `version: "1.0"`
- `node: "saver"` with `version: "1.0"`
