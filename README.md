# Data Pipeline Agent
An autonomous, tool-driven AI agent that takes raw data → cleans it → visualizes it → builds a report → emails it.

## What This Project Does
This agent:
1. Plans a pipeline
2. Fetches raw data (with retry logic)
3. Cleans & transforms it using pandas
4. Generates charts (matplotlib)
5. Builds a markdown report
6. Sends it via email (simulated)
All of this is orchestrated through an intelligent agent loop.
