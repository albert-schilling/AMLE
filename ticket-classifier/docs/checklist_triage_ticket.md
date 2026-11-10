
# Improvements for the Triage prototype script:

- feature missing: team assignment
- examples for JSON output in prompt
- validate the result with LLM or other
- user can do prompt injection
- user could submit very long text, set maximum length
- monitor token usage/limits
- use a generic library to make it easy to switch to a different LLM (e.g. [OpenAI Docs](https://developers.openai.com/api/docs/libraries))

## Done

- API key is in the code ✅
- code is not on GitHub ✅
- filename not ideal ✅
- should import data from JSON file ✅
- API key should be in .env file, use it in Python file ✅
- no .gitignore ✅ (there is one at the repo root)
- split prompt in system + user prompt ✅
- explicitly add expected output format (e.g. JSON) ✅
- package environment: py version + lib version, pyproject.toml ✅
- make categories a Literal ✅
- use structured output of the model ✅
- create a uv environment ✅
- write unit test for the script ✅
- the unit test must not consume tokens -> there should be a way to test without connecting to the API (mock, stub, monkeypatch, config setting) ✅
- uv python pin 3.13.17 ✅
- uv init --bare ✅
- regex for validation 🚫 (superseded by Structured Output [Pydantic Class / Dict])
- uses haiku by default (cheap, good) ✅
- make options (model + max tokens) configurable (pydantic, configparser) ✅
- no error handling (try.. except) ✅
