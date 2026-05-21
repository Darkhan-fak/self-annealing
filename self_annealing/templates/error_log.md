# Error Log

This log keeps track of resolved errors, their causes, and their fixes, allowing AI agents to quickly search for existing solutions and prevent repeating previous mistakes.

## Error E001
- **Symptom**: [TEMPLATE] MQTT rc=5 auth failure
- **Cause**: Invalid credentials provided to the MQTT broker
- **Fix**: Check MQTT_USER and MQTT_PASS in .env
- **Context**: mqtt
- **Tokens**: 500

## Error E002
- **Symptom**: [TEMPLATE] Railway PORT binding failed
- **Cause**: App is hardcoded to listen on a specific port (e.g. 8000), but Railway expects it to bind to the environment variable $PORT
- **Fix**: Read port from OS environment: port = int(os.environ.get("PORT", 8000))
- **Context**: deploy
- **Tokens**: 400

## Error E003
- **Symptom**: [TEMPLATE] Connection refused on localhost:5432
- **Cause**: PostgreSQL server is not running locally
- **Fix**: Start the PostgreSQL service using: sudo systemctl start postgresql (Linux) or check your local service manager
- **Context**: database
- **Tokens**: 300

## Error E004
- **Symptom**: [TEMPLATE] ModuleNotFoundError: No module named 'colorama'
- **Cause**: The colorama package is not installed in the current environment
- **Fix**: Install colorama using pip: pip install colorama, or add it to pyproject.toml / requirements.txt
- **Context**: environment
- **Tokens**: 200

## Error E005
- **Symptom**: [TEMPLATE] Permission denied for config.json
- **Cause**: The file config.json does not have read permissions for the current user
- **Fix**: Run chmod +r config.json or check file ownership
- **Context**: permissions
- **Tokens**: 150
