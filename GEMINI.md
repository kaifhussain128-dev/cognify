# Project Guidelines & Rules

## Security & Secrets Protection

- **Do NOT read or access `.env`**: Under no circumstances should the agent use any tool to inspect, read, print, display, or edit the `.env` file or any `.env.*` / secret credential files.
- **Do NOT expose secrets**: Never print or leak secret keys, tokens, or contents from environment variable files in tool outputs, responses, or artifacts.
- **File Listings**: When listing or summarizing the files in this repository, exclude `.env` and any secret files from the output.
